/**
 * Multi-Camera GeoVision + RGM Stream Viewer
 * Layout: GeoVision RGB | GeoVision Thermal | RGM Thermal (per row)
 */

(function() {
  'use strict';

  // ==================== Configuration ====================
  
  // GeoVision API uses normalized coordinates (0-10000)
  const thermalConfig = window.THERMAL_CONFIG || { apiCoordMax: 10000 };
  const rgmAvailable = window.RGM_AVAILABLE || false;
  
  console.log('[Config] Thermal API coordinate max:', thermalConfig.apiCoordMax);
  console.log('[Config] RGM available:', rgmAvailable);

  // ==================== State Management ====================
  
  // Track temperature measurement state per camera
  const cameraStates = new Map();
  
  function getCameraState(cameraId) {
    if (!cameraStates.has(cameraId)) {
      cameraStates.set(cameraId, {
        selectedPoint: null,
        refreshInterval: null
      });
    }
    return cameraStates.get(cameraId);
  }

  // ==================== Coordinate Calculation ====================
  
  /**
   * Calculate API coordinates from click event on thermal image
   * GeoVision API uses normalized coordinates (0-10000)
   */
  function getApiCoordinates(event, thermalImg) {
    if (!thermalImg) {
      console.warn('[Coords] No thermal image provided');
      return null;
    }

    const imgRect = thermalImg.getBoundingClientRect();
    
    // Validate image has dimensions
    if (imgRect.width <= 0 || imgRect.height <= 0) {
      console.warn('[Coords] Image has no dimensions:', imgRect);
      return null;
    }

    const clickX = event.clientX - imgRect.left;
    const clickY = event.clientY - imgRect.top;

    // Validate click is within bounds
    if (clickX < 0 || clickY < 0 || clickX > imgRect.width || clickY > imgRect.height) {
      console.warn('[Coords] Click outside image bounds');
      return null;
    }

    // Calculate percentage position (clamped to 0-1)
    const percentX = Math.max(0, Math.min(1, clickX / imgRect.width));
    const percentY = Math.max(0, Math.min(1, clickY / imgRect.height));

    // Map to API coordinate space (0-10000)
    const apiMax = thermalConfig.apiCoordMax || 10000;
    const apiX = Math.round(percentX * apiMax);
    const apiY = Math.round(percentY * apiMax);

    console.log('[Coords] Click mapped:', {
      percent: { x: (percentX * 100).toFixed(1) + '%', y: (percentY * 100).toFixed(1) + '%' },
      apiCoords: { x: apiX, y: apiY }
    });

    return {
      x: apiX,
      y: apiY,
      displayX: clickX,
      displayY: clickY,
      percentX: percentX,
      percentY: percentY
    };
  }

  // ==================== Temperature API ====================
  
  /**
   * Fetch temperature for a camera at given coordinates
   */
  async function fetchTemperature(cameraId, x, y) {
    const url = `/api/cameras/${encodeURIComponent(cameraId)}/temperature?x=${x}&y=${y}`;
    console.log(`[Temp] Fetching: ${url}`);
    
    try {
      const response = await fetch(url);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error(`[Temp] HTTP ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      console.log(`[Temp] Camera ${cameraId}: ${data.temperature}°C at (${x}, ${y})`);
      return data;
    } catch (error) {
      console.error(`[Temp] Error for camera ${cameraId}:`, error);
      return null;
    }
  }

  // ==================== UI Updates ====================
  
  /**
   * Update temperature overlay for a camera
   */
  function updateTempOverlay(container, coords, tempData) {
    const overlay = container.querySelector('.thermal-overlay');
    const crosshair = container.querySelector('.thermal-crosshair');
    const tempDisplay = container.querySelector('.thermal-temp');

    if (!overlay || !crosshair || !tempDisplay) return;

    if (tempData && tempData.temperature !== undefined) {
      tempDisplay.textContent = `${tempData.temperature} °C`;
    } else {
      tempDisplay.textContent = 'Error';
    }

    crosshair.style.left = coords.displayX + 'px';
    crosshair.style.top = coords.displayY + 'px';
    tempDisplay.style.left = coords.displayX + 'px';
    tempDisplay.style.top = coords.displayY + 'px';
    overlay.style.display = 'block';
  }

  /**
   * Refresh temperature at selected point for a camera
   */
  async function refreshTemperature(cameraId) {
    const state = getCameraState(cameraId);
    if (!state.selectedPoint) return;

    const tempData = await fetchTemperature(cameraId, state.selectedPoint.x, state.selectedPoint.y);
    
    const container = document.querySelector(`.thermal-container[data-camera-id="${cameraId}"]`);
    if (container && tempData) {
      updateTempOverlay(container, state.selectedPoint, tempData);
    }
  }

  // ==================== Event Handlers ====================
  
  /**
   * Handle click on thermal image or its container
   */
  async function handleThermalClick(event) {
    // Find the thermal container - click might be on image or container
    const container = event.target.closest('.thermal-container');
    if (!container) {
      console.error('[Click] Could not find thermal container');
      return;
    }
    
    // Get camera ID from container (more reliable than image)
    const cameraId = container.dataset.cameraId;
    if (!cameraId) {
      console.error('[Click] No camera ID on thermal container');
      return;
    }
    
    // Get the thermal image for coordinate calculation
    const thermalImg = container.querySelector('.thermal-img');
    if (!thermalImg) {
      console.error('[Click] No thermal image found in container');
      return;
    }

    console.log(`[Click] Camera: ${cameraId}`);

    const coords = getApiCoordinates(event, thermalImg);
    if (!coords) return;

    const state = getCameraState(cameraId);
    state.selectedPoint = coords;

    // Show loading
    const tempDisplay = container.querySelector('.thermal-temp');
    if (tempDisplay) tempDisplay.textContent = 'Loading...';
    updateTempOverlay(container, coords, null);

    // Fetch temperature
    const tempData = await fetchTemperature(cameraId, coords.x, coords.y);
    if (tempData) {
      updateTempOverlay(container, coords, tempData);
    } else {
      if (tempDisplay) tempDisplay.textContent = 'Error';
    }

    // Setup auto-refresh
    if (state.refreshInterval) {
      clearInterval(state.refreshInterval);
    }
    state.refreshInterval = setInterval(() => refreshTemperature(cameraId), 1000);
  }

  // ==================== Camera Management ====================
  
  /**
   * Add a new camera via API
   */
  async function addCamera(formData) {
    try {
      const response = await fetch('/api/cameras', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });
      
      const result = await response.json();
      
      if (!response.ok) {
        throw new Error(result.error || 'Failed to add camera');
      }
      
      return result;
    } catch (error) {
      console.error('[Camera] Add failed:', error);
      throw error;
    }
  }

  /**
   * Remove a camera via API
   * Exposed globally for onclick handlers
   */
  async function removeCameraById(cameraId) {
    console.log(`[Camera] Attempting to remove: ${cameraId}`);
    
    if (!cameraId) {
      console.error('[Camera] No camera ID provided');
      alert('Error: No camera ID');
      return;
    }
    
    if (!confirm('Remove this camera?')) return;
    
    try {
      const response = await fetch(`/api/cameras/${encodeURIComponent(cameraId)}`, {
        method: 'DELETE'
      });
      
      console.log(`[Camera] Delete response status: ${response.status}`);
      
      if (response.ok) {
        // Remove from DOM
        const row = document.querySelector(`.camera-row[data-camera-id="${cameraId}"]`);
        if (row) {
          row.remove();
          console.log(`[Camera] Removed row from DOM`);
        } else {
          console.warn(`[Camera] Could not find row in DOM for: ${cameraId}`);
        }
        
        // Clean up state
        if (cameraStates.has(cameraId)) {
          const state = cameraStates.get(cameraId);
          if (state.refreshInterval) {
            clearInterval(state.refreshInterval);
          }
          cameraStates.delete(cameraId);
        }
        
        // Show RGM-only row if no cameras left
        checkNoCameras();
        
        console.log(`[Camera] Successfully removed: ${cameraId}`);
      } else {
        let errorMsg = 'Failed to remove camera';
        try {
          const result = await response.json();
          errorMsg = result.error || errorMsg;
        } catch (e) {
          // Response might not be JSON
        }
        console.error(`[Camera] Remove failed: ${errorMsg}`);
        alert(errorMsg);
      }
    } catch (error) {
      console.error('[Camera] Remove request failed:', error);
      alert('Failed to remove camera: ' + error.message);
    }
  }
  
  // Expose to global scope for onclick handlers
  window.removeCamera = removeCameraById;

  /**
   * Create camera row HTML with triple grid (RGB | Thermal | RGM)
   */
  function createCameraRow(camera) {
    if (!camera || !camera.id) {
      console.error('[CreateRow] Invalid camera data:', camera);
      return null;
    }
    
    const row = document.createElement('div');
    row.className = 'camera-row';
    row.dataset.cameraId = camera.id;
    
    // Escape values for safe HTML insertion
    const safeId = escapeAttr(camera.id);
    const safeName = escapeHtml(camera.name || 'Unnamed Camera');
    const safeIp = escapeHtml(camera.ip_address || 'Unknown IP');
    
    const rgmContent = rgmAvailable 
      ? `<img src="/video/rgm" alt="RGM Thermal Stream" />
         <div class="rgm-temp-badge rgm-temp-display">Center: -- °C</div>`
      : `<div class="stream-placeholder">
           <p>RGM camera unavailable</p>
         </div>`;
    
    row.innerHTML = `
      <div class="camera-row-header">
        <h2>${safeName}</h2>
        <span class="camera-ip">${safeIp}</span>
        <button class="btn-remove" data-remove-camera="${safeId}" title="Remove camera">✕</button>
      </div>
      <div class="triple-stream-grid">
        <!-- GeoVision RGB -->
        <section class="stream">
          <h3>GeoVision RGB</h3>
          <img src="/video/${encodeURIComponent(camera.id)}/rgb" alt="RGB Stream" />
        </section>
        <!-- GeoVision Thermal -->
        <section class="stream">
          <h3>GeoVision Thermal <span class="stream-hint">(Click to measure)</span></h3>
          <div class="stream-container thermal-container" data-camera-id="${safeId}">
            <img class="thermal-img clickable" 
                 data-camera-id="${safeId}" 
                 src="/video/${encodeURIComponent(camera.id)}/thermal" 
                 alt="Thermal Stream" />
            <div class="thermal-overlay">
              <div class="thermal-crosshair"></div>
              <div class="thermal-temp"></div>
            </div>
          </div>
        </section>
        <!-- RGM Thermal -->
        <section class="stream rgm-stream">
          <h3>RGM Thermal <span class="stream-hint">(Center temp)</span></h3>
          <div class="stream-container rgm-container">
            ${rgmContent}
          </div>
        </section>
      </div>
    `;
    
    // Add click handler for thermal image
    const thermalImg = row.querySelector('.thermal-img');
    if (thermalImg) {
      thermalImg.addEventListener('click', handleThermalClick);
      console.log(`[CreateRow] Attached click handler for camera: ${camera.id}`);
    }
    
    return row;
  }

  /**
   * Check if we need to show "RGM only" row when no cameras exist
   */
  function checkNoCameras() {
    const container = document.getElementById('cameras-container');
    const cameraRows = container.querySelectorAll('.camera-row:not(.rgm-only-row)');
    let rgmOnlyRow = document.getElementById('rgm-only-row');
    
    if (cameraRows.length === 0) {
      // No cameras - show RGM only row
      if (!rgmOnlyRow) {
        const rgmContent = rgmAvailable 
          ? `<img src="/video/rgm" alt="RGM Thermal Stream" />
             <div class="rgm-temp-badge rgm-temp-display">Center: -- °C</div>`
          : `<div class="stream-placeholder">
               <p>RGM camera unavailable</p>
               <p class="hint">Add a GeoVision camera above to start monitoring</p>
             </div>`;
        
        rgmOnlyRow = document.createElement('div');
        rgmOnlyRow.className = 'camera-row rgm-only-row';
        rgmOnlyRow.id = 'rgm-only-row';
        rgmOnlyRow.innerHTML = `
          <div class="camera-row-header">
            <h2>RGM Local Thermal</h2>
            <span class="camera-ip">USB Connected</span>
          </div>
          <div class="single-stream-grid">
            <section class="stream rgm-stream">
              <h3>RGM Thermal <span class="stream-hint">(Center temperature)</span></h3>
              <div class="stream-container rgm-container">
                ${rgmContent}
              </div>
            </section>
          </div>
        `;
        container.appendChild(rgmOnlyRow);
      }
    } else if (rgmOnlyRow) {
      // Have cameras - remove RGM only row
      rgmOnlyRow.remove();
    }
  }

  /**
   * Escape HTML to prevent XSS
   */
  function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
  }
  
  /**
   * Escape for HTML attribute values (more strict than escapeHtml)
   */
  function escapeAttr(text) {
    if (text === null || text === undefined) return '';
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  // ==================== RGM Temperature Polling ====================
  
  let rgmPollHandle = null;
  
  /**
   * Update ALL RGM temperature displays (one in each camera row)
   */
  async function pollRgmTemperature() {
    if (!rgmAvailable) return;

    try {
      const response = await fetch('/rgm/center_temperature');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      
      const data = await response.json();
      
      // Update ALL RGM temperature displays
      const rgmDisplays = document.querySelectorAll('.rgm-temp-display');
      
      rgmDisplays.forEach(display => {
        if (typeof data.temp_c === 'number') {
          const valueC = data.temp_c.toFixed(2);
          const valueF = typeof data.temp_f === 'number' ? data.temp_f.toFixed(2) : null;
          display.textContent = valueF
            ? `Center: ${valueC} °C (${valueF} °F)`
            : `Center: ${valueC} °C`;
          display.classList.remove('muted');
        } else {
          display.textContent = 'Center: -- °C';
          display.classList.add('muted');
        }
      });
    } catch (error) {
      console.error('[RGM] Poll error:', error);
      document.querySelectorAll('.rgm-temp-display').forEach(display => {
        display.textContent = 'Center: -- °C';
        display.classList.add('muted');
      });
    }
    
    rgmPollHandle = setTimeout(pollRgmTemperature, 1000);
  }

  // ==================== Initialization ====================
  
  function init() {
    console.log('[Init] Multi-camera viewer starting...');
    
    // Setup add camera form
    const addForm = document.getElementById('add-camera-form');
    const addStatus = document.getElementById('add-camera-status');
    
    if (addForm) {
      addForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        
        const formData = {
          name: addForm.querySelector('[name="name"]').value.trim(),
          ip_address: addForm.querySelector('[name="ip_address"]').value.trim(),
          username: addForm.querySelector('[name="username"]').value.trim(),
          password: addForm.querySelector('[name="password"]').value
        };
        
        addStatus.textContent = 'Adding camera...';
        addStatus.className = 'config-status muted';
        
        try {
          const result = await addCamera(formData);
          
          if (!result || !result.camera) {
            throw new Error('Invalid response from server');
          }
          
          // Remove RGM-only row if present
          const rgmOnlyRow = document.getElementById('rgm-only-row');
          if (rgmOnlyRow) rgmOnlyRow.remove();
          
          // Add camera row to DOM
          const container = document.getElementById('cameras-container');
          const row = createCameraRow(result.camera);
          
          if (row) {
            container.appendChild(row);
          } else {
            throw new Error('Failed to create camera row');
          }
          
          // Clear form
          addForm.reset();
          addForm.querySelector('[name="username"]').value = 'admin';
          
          addStatus.textContent = `Added: ${result.camera.name || 'Camera'}`;
          addStatus.className = 'config-status success';
          
          setTimeout(() => {
            addStatus.textContent = '';
          }, 3000);
          
        } catch (error) {
          addStatus.textContent = error.message || 'Failed to add camera';
          addStatus.className = 'config-status error';
        }
      });
    }
    
    // Setup existing thermal image click handlers
    // Attach to container for more reliable click detection
    document.querySelectorAll('.thermal-container[data-camera-id]').forEach(container => {
      const img = container.querySelector('.thermal-img');
      if (img) {
        img.addEventListener('click', handleThermalClick);
        console.log(`[Init] Attached click handler for camera: ${container.dataset.cameraId}`);
      }
    });
    
    // Setup event delegation for remove buttons (more reliable than inline onclick)
    document.addEventListener('click', function(event) {
      const removeBtn = event.target.closest('[data-remove-camera]');
      if (removeBtn) {
        const cameraId = removeBtn.dataset.removeCamera;
        console.log(`[Click] Remove button clicked for camera: ${cameraId}`);
        removeCameraById(cameraId);
      }
    });
    
    // Start RGM polling if available
    if (rgmAvailable) {
      pollRgmTemperature();
    }
    
    console.log('[Init] Ready');
  }

  // Start when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
