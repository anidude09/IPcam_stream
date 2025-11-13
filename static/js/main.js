/**
 * GeoVision Stream Viewer - Main JavaScript
 * Handles thermal stream temperature measurement functionality
 */

(function() {
  'use strict';

  // DOM Elements
  const thermalImg = document.getElementById('thermal-img');
  const thermalContainer = document.getElementById('thermal-container');
  const thermalOverlay = document.getElementById('thermal-overlay');
  const thermalCrosshair = document.getElementById('thermal-crosshair');
  const thermalTemp = document.getElementById('thermal-temp');

  // State
  let selectedPoint = null;
  let refreshInterval = null;
  
  // Coordinate system configuration
  // If camera uses flipped X coordinates (0,0 at top-right instead of top-left)
  // Set this to true to flip X: cameraX = naturalWidth - 1 - calculatedX
  let flipXCoordinates = false;  // Set to true if (0,0) appears at top-right

  /**
   * Calculate image coordinates from click event
   * Converts click position to actual video frame pixel coordinates
   * @param {MouseEvent} event - Click event
   * @returns {Object|null} Object with frame coordinates (x, y) and display coordinates (displayX, displayY)
   */
  function getImageCoords(event) {
    // Wait for image to be loaded and have natural dimensions
    // For MJPEG streams, we need to wait for the first frame to load
    if (thermalImg.complete === false || thermalImg.naturalWidth === 0 || thermalImg.naturalHeight === 0) {
      console.warn('[Coordinate Calc] Image not fully loaded. naturalWidth:', thermalImg.naturalWidth, 'naturalHeight:', thermalImg.naturalHeight);
      // Try to use current image dimensions as fallback
      const imgRect = thermalImg.getBoundingClientRect();
      if (imgRect.width === 0 || imgRect.height === 0) {
        return null;
      }
    }

    // Get image bounding rectangle (position and size on screen)
    const imgRect = thermalImg.getBoundingClientRect();

    // Calculate click position relative to the image element (not viewport)
    const clickX = event.clientX - imgRect.left;
    const clickY = event.clientY - imgRect.top;

    // Get actual image dimensions
    // For MJPEG, naturalWidth/Height should be available after first frame loads
    const naturalWidth = thermalImg.naturalWidth;
    const naturalHeight = thermalImg.naturalHeight;

    // Validate dimensions
    if (naturalWidth === 0 || naturalHeight === 0 || imgRect.width === 0 || imgRect.height === 0) {
      console.error('[Coordinate Calc] Invalid dimensions:', {
        natural: { width: naturalWidth, height: naturalHeight },
        displayed: { width: imgRect.width, height: imgRect.height }
      });
      return null;
    }

    // Calculate scale factors (how much the image is scaled from natural size)
    const scaleX = naturalWidth / imgRect.width;
    const scaleY = naturalHeight / imgRect.height;

    // Calculate actual pixel coordinates in the video frame
    // Clamp to valid range to prevent out-of-bounds coordinates
    let frameX = Math.max(0, Math.min(naturalWidth - 1, Math.round(clickX * scaleX)));
    let frameY = Math.max(0, Math.min(naturalHeight - 1, Math.round(clickY * scaleY)));
    
    // Check if camera coordinate system is flipped horizontally
    // If (0,0) appears at top-right, we need to flip X coordinate
    // Camera uses: cameraX = naturalWidth - 1 - frameX
    const cameraX = flipXCoordinates ? (naturalWidth - 1 - frameX) : frameX;
    const cameraY = frameY;
    
    if (flipXCoordinates) {
      console.log('[Coordinate Calc] X coordinate flipped:', {
        calculatedX: frameX,
        cameraX: cameraX,
        naturalWidth: naturalWidth
      });
    }

    // Debug logging with detailed information
    console.log('[Coordinate Calc] Detailed calculation:', {
      clickPos: { 
        clientX: event.clientX, 
        clientY: event.clientY,
        relativeX: clickX.toFixed(2), 
        relativeY: clickY.toFixed(2) 
      },
      imageRect: { 
        left: imgRect.left.toFixed(2), 
        top: imgRect.top.toFixed(2),
        width: imgRect.width.toFixed(2), 
        height: imgRect.height.toFixed(2) 
      },
      naturalDimensions: { 
        width: naturalWidth, 
        height: naturalHeight 
      },
      scaleFactors: { 
        x: scaleX.toFixed(4), 
        y: scaleY.toFixed(4) 
      },
      calculatedFrameCoords: { 
        x: frameX, 
        y: frameY 
      },
      cameraCoords: {
        x: cameraX,
        y: cameraY
      },
      validation: {
        xInRange: frameX >= 0 && frameX < naturalWidth,
        yInRange: frameY >= 0 && frameY < naturalHeight
      }
    });

    // Return coordinates - keep original clicked position for display
    return {
      x: cameraX,          // Frame coordinates sent to API (may need X flip)
      y: cameraY,          // Frame coordinates sent to API
      displayX: clickX,    // Display coordinates (keep original click position)
      displayY: clickY,    // Display coordinates (keep original click position)
      originalX: cameraX,  // Store original for reference
      originalY: cameraY,  // Store original for reference
      calculatedX: frameX, // Store calculated X before potential flip
      calculatedY: frameY  // Store calculated Y
    };
  }

  /**
   * Fetch temperature from API for given coordinates
   * @param {number} x - X coordinate in video frame
   * @param {number} y - Y coordinate in video frame
   * @returns {Promise<Object|null>} Temperature data or null on error
   */
  async function fetchTemperature(x, y) {
    try {
      console.log(`[API Call] Fetching temperature for coordinates: x=${x}, y=${y}`);
      const response = await fetch(`/temperature?x=${x}&y=${y}`);
      if (!response.ok) {
        const errorText = await response.text();
        console.error(`[API Call] HTTP error ${response.status}:`, errorText);
        throw new Error(`Failed to fetch temperature: ${response.status}`);
      }
      const data = await response.json();
      console.log('[API Call] Response received:', data);
      return data;
    } catch (error) {
      console.error('[API Call] Temperature fetch error:', error);
      return null;
    }
  }

  /**
   * Update the temperature display overlay
   * @param {Object} coords - Coordinates object with displayX and displayY
   * @param {Object} tempData - Temperature data from API
   */
  function updateTemperatureDisplay(coords, tempData) {
    if (!tempData) {
      thermalTemp.textContent = 'Error';
      return;
    }

    thermalTemp.textContent = `${tempData.temperature} °C`;
    thermalCrosshair.style.left = coords.displayX + 'px';
    thermalCrosshair.style.top = coords.displayY + 'px';
    thermalTemp.style.left = coords.displayX + 'px';
    thermalTemp.style.top = coords.displayY + 'px';
    thermalOverlay.style.display = 'block';
  }

  /**
   * Recalculate display coordinates from frame coordinates
   * Used for window resize - keeps overlay at correct position
   * @param {Object} point - Point object with x, y frame coordinates
   * @returns {Object} Updated point with displayX and displayY
   */
  function recalculateDisplayCoords(point) {
    const imgRect = thermalImg.getBoundingClientRect();
    const naturalWidth = thermalImg.naturalWidth || imgRect.width;
    const naturalHeight = thermalImg.naturalHeight || imgRect.height;

    if (naturalWidth > 0 && naturalHeight > 0) {
      const scaleX = imgRect.width / naturalWidth;
      const scaleY = imgRect.height / naturalHeight;
      // Use original coordinates if available, otherwise use current x/y
      const frameX = point.originalX !== undefined ? point.originalX : point.x;
      const frameY = point.originalY !== undefined ? point.originalY : point.y;
      point.displayX = frameX * scaleX;
      point.displayY = frameY * scaleY;
    }
    return point;
  }

  /**
   * Refresh temperature at the currently selected point
   * Uses original clicked coordinates, not camera's confirmed coordinates
   */
  async function refreshTemperature() {
    if (!selectedPoint) return;

    // Always use the original clicked coordinates, not camera's response
    const originalX = selectedPoint.originalX !== undefined ? selectedPoint.originalX : selectedPoint.x;
    const originalY = selectedPoint.originalY !== undefined ? selectedPoint.originalY : selectedPoint.y;

    console.log(`[Refresh] Using original coordinates: x=${originalX}, y=${originalY}`);
    
    const tempData = await fetchTemperature(originalX, originalY);
    if (tempData) {
      // Log if camera returns different coordinates
      if (tempData.x !== originalX || tempData.y !== originalY) {
        console.log(`[Refresh] Camera confirmed coords differ: requested (${originalX}, ${originalY}), got (${tempData.x}, ${tempData.y})`);
      }
      
      // Keep using original clicked coordinates for display
      // Don't update selectedPoint.x/y to camera's response
      updateTemperatureDisplay(selectedPoint, tempData);
    }
  }

  /**
   * Handle click on thermal image
   */
  async function handleThermalClick(event) {
    const coords = getImageCoords(event);
    if (!coords) {
      console.warn('Image not loaded yet, please wait...');
      return;
    }

    selectedPoint = coords;

    // Show loading state
    thermalTemp.textContent = 'Loading...';
    thermalCrosshair.style.left = coords.displayX + 'px';
    thermalCrosshair.style.top = coords.displayY + 'px';
    thermalTemp.style.left = coords.displayX + 'px';
    thermalTemp.style.top = coords.displayY + 'px';
    thermalOverlay.style.display = 'block';

    // Fetch initial temperature
    const tempData = await fetchTemperature(coords.x, coords.y);
    if (tempData) {
      // Log if camera returns different coordinates
      if (tempData.x !== coords.x || tempData.y !== coords.y) {
        console.log(`[Click] Camera confirmed coords differ: clicked (${coords.x}, ${coords.y}), camera returned (${tempData.x}, ${tempData.y})`);
      }
      
      // Keep original clicked coordinates - don't update to camera's response
      // The crosshair stays at the clicked location
      updateTemperatureDisplay(coords, tempData);
    }

    // Clear existing interval and start auto-refresh every 1 second
    if (refreshInterval) {
      clearInterval(refreshInterval);
    }
    refreshInterval = setInterval(refreshTemperature, 1000); // Changed from 2000ms to 1000ms
  }

  /**
   * Update overlay position on window resize
   */
  function handleResize() {
    if (selectedPoint) {
      const imgRect = thermalImg.getBoundingClientRect();
      const naturalWidth = thermalImg.naturalWidth || imgRect.width;
      const naturalHeight = thermalImg.naturalHeight || imgRect.height;

      if (naturalWidth > 0 && naturalHeight > 0) {
        recalculateDisplayCoords(selectedPoint);
        thermalCrosshair.style.left = selectedPoint.displayX + 'px';
        thermalCrosshair.style.top = selectedPoint.displayY + 'px';
        thermalTemp.style.left = selectedPoint.displayX + 'px';
        thermalTemp.style.top = selectedPoint.displayY + 'px';
      }
    }
  }

  /**
   * Handle image load event to recalculate positions
   */
  function handleImageLoad() {
    if (selectedPoint) {
      const imgRect = thermalImg.getBoundingClientRect();
      const naturalWidth = thermalImg.naturalWidth || imgRect.width;
      const naturalHeight = thermalImg.naturalHeight || imgRect.height;

      if (naturalWidth > 0 && naturalHeight > 0) {
        console.log('[Image Load] Natural dimensions available:', { width: naturalWidth, height: naturalHeight });
        recalculateDisplayCoords(selectedPoint);
        thermalCrosshair.style.left = selectedPoint.displayX + 'px';
        thermalCrosshair.style.top = selectedPoint.displayY + 'px';
        thermalTemp.style.left = selectedPoint.displayX + 'px';
        thermalTemp.style.top = selectedPoint.displayY + 'px';
      }
    }
  }

  /**
   * Initialize temperature measurement at origin (0,0)
   * Called when the image loads to automatically start measuring at origin
   * NOTE: If (0,0) appears at top-right, the camera may use flipped X coordinates
   */
  async function initializeOriginMeasurement() {
    // Wait for image to be loaded with natural dimensions
    if (thermalImg.naturalWidth === 0 || thermalImg.naturalHeight === 0) {
      console.log('[Init] Waiting for image to load...');
      return;
    }

    const imgRect = thermalImg.getBoundingClientRect();
    if (imgRect.width === 0 || imgRect.height === 0) {
      console.log('[Init] Image not yet displayed, waiting...');
      return;
    }

    // Calculate display position for (0,0) coordinates
    const naturalWidth = thermalImg.naturalWidth;
    const naturalHeight = thermalImg.naturalHeight;
    const scaleX = imgRect.width / naturalWidth;
    const scaleY = imgRect.height / naturalHeight;

    // If camera uses flipped X coordinates, (0,0) in camera space is at top-right
    // To show marker at top-left (visual 0,0), we need to send (naturalWidth-1, 0) to camera
    // But if flipXCoordinates is true, the transformation happens in getImageCoords
    // So for display at top-left, we calculate what camera coordinate that would be
    const testOriginX = flipXCoordinates ? (naturalWidth - 1) : 0;
    const testOriginY = 0;
    
    // Display coordinates for origin (0,0) - this should be top-left of displayed image
    const displayX = 0;  // Top-left corner of displayed image
    const displayY = 0;  // Top-left corner of displayed image

    console.log('[Init] Testing origin coordinates:', {
      naturalDimensions: { width: naturalWidth, height: naturalHeight },
      testCoords: { x: testOriginX, y: testOriginY },
      displayPos: { x: displayX, y: displayY },
      flipXEnabled: flipXCoordinates
    });

    // Create coordinate object for origin
    const originCoords = {
      x: testOriginX,
      y: testOriginY,
      displayX: displayX,
      displayY: displayY,
      originalX: testOriginX,
      originalY: testOriginY,
      calculatedX: testOriginX,
      calculatedY: testOriginY
    };

    console.log('[Init] Initializing temperature measurement at origin (0,0)');
    console.log('[Init] Display position:', { displayX, displayY, scaleX, scaleY });

    // Set as selected point
    selectedPoint = originCoords;

    // Show crosshair and loading state at origin
    thermalTemp.textContent = 'Loading...';
    thermalCrosshair.style.left = displayX + 'px';
    thermalCrosshair.style.top = displayY + 'px';
    thermalTemp.style.left = displayX + 'px';
    thermalTemp.style.top = displayY + 'px';
    thermalOverlay.style.display = 'block';

    // Fetch initial temperature at origin
    // If (0,0) appears at top-right, we may need to use (naturalWidth-1, 0) instead
    const testX = testOriginX;
    const testY = testOriginY;
    
    console.log('[Init] Fetching temperature at:', { x: testX, y: testY, naturalWidth });
    const tempData = await fetchTemperature(testX, testY);
    if (tempData) {
      console.log('[Init] Temperature at origin:', tempData);
      console.log('[Init] If marker appears at top-right, camera may use flipped X coordinates');
      console.log('[Init] Try clicking top-left corner to see what coordinates it reports');
      updateTemperatureDisplay(originCoords, tempData);
    } else {
      thermalTemp.textContent = 'Error';
    }

    // Start auto-refresh interval
    if (refreshInterval) {
      clearInterval(refreshInterval);
    }
    refreshInterval = setInterval(refreshTemperature, 1000);
  }

  // Event Listeners
  if (thermalImg) {
    thermalImg.addEventListener('click', handleThermalClick);
    thermalImg.addEventListener('load', function() {
      handleImageLoad();
      // Initialize origin measurement when image loads
      // Use a small delay to ensure dimensions are fully available
      setTimeout(initializeOriginMeasurement, 500);
    });
  }

  // Also try to initialize if image is already loaded
  if (thermalImg && thermalImg.complete && thermalImg.naturalWidth > 0) {
    setTimeout(initializeOriginMeasurement, 500);
  }

  // Debounced resize handler
  let resizeTimeout;
  window.addEventListener('resize', function() {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(handleResize, 100);
  });
})();

