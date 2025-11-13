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

  /**
   * Calculate image coordinates from click event
   * Converts click position to actual video frame pixel coordinates
   * @param {MouseEvent} event - Click event
   * @returns {Object|null} Object with frame coordinates (x, y) and display coordinates (displayX, displayY)
   */
  function getImageCoords(event) {
    // Get container and image positions relative to container
    const imgRect = thermalImg.getBoundingClientRect();

    // Calculate click position relative to the image (not viewport)
    const clickX = event.clientX - imgRect.left;
    const clickY = event.clientY - imgRect.top;

    // For MJPEG streams, naturalWidth/Height might not be reliable
    // Use displayed dimensions as fallback if natural dimensions aren't available
    const naturalWidth = thermalImg.naturalWidth || imgRect.width;
    const naturalHeight = thermalImg.naturalHeight || imgRect.height;

    if (naturalWidth === 0 || naturalHeight === 0) {
      console.warn('[Coordinate Calc] Image dimensions not available yet');
      return null;
    }

    // Calculate scale factors
    const scaleX = naturalWidth / imgRect.width;
    const scaleY = naturalHeight / imgRect.height;

    // Calculate actual pixel coordinates in the video frame
    const frameX = Math.round(clickX * scaleX);
    const frameY = Math.round(clickY * scaleY);

    // Debug logging
    console.log('[Coordinate Calc]', {
      clickPos: { x: clickX, y: clickY },
      imgRect: { width: imgRect.width, height: imgRect.height },
      natural: { width: naturalWidth, height: naturalHeight },
      scale: { x: scaleX, y: scaleY },
      frameCoords: { x: frameX, y: frameY }
    });

    // Display coordinates are relative to the container (for overlay positioning)
    return {
      x: frameX,
      y: frameY,
      displayX: clickX,
      displayY: clickY
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
      point.displayX = point.x * scaleX;
      point.displayY = point.y * scaleY;
    }
    return point;
  }

  /**
   * Refresh temperature at the currently selected point
   */
  async function refreshTemperature() {
    if (!selectedPoint) return;

    const tempData = await fetchTemperature(selectedPoint.x, selectedPoint.y);
    if (tempData) {
      // Update selected point with camera's confirmed coordinates
      selectedPoint.x = tempData.x;
      selectedPoint.y = tempData.y;

      // Recalculate display position based on updated coordinates
      recalculateDisplayCoords(selectedPoint);
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
      // Update with camera's confirmed coordinates
      selectedPoint.x = tempData.x;
      selectedPoint.y = tempData.y;

      // Recalculate display position if coordinates changed
      recalculateDisplayCoords(selectedPoint);
      updateTemperatureDisplay(selectedPoint, tempData);
    }

    // Clear existing interval and start auto-refresh
    if (refreshInterval) {
      clearInterval(refreshInterval);
    }
    refreshInterval = setInterval(refreshTemperature, 2000);
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

  // Event Listeners
  if (thermalImg) {
    thermalImg.addEventListener('click', handleThermalClick);
    thermalImg.addEventListener('load', handleImageLoad);
  }

  // Debounced resize handler
  let resizeTimeout;
  window.addEventListener('resize', function() {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(handleResize, 100);
  });
})();

