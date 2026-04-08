# -*- coding: utf-8 -*-
"""
Leaflet Viewport Loading Template.

JavaScript template for viewport-based building loading.
Loads only visible buildings, with debouncing and dynamic marker updates.
"""

VIEWPORT_LOADING_JS_TEMPLATE = '''
        // =========================================================
        // Viewport-Based Loading
        // =========================================================

        // Define getStatusKey if not already defined (for viewport loading)
        if (typeof getStatusKey === 'undefined') {
            var statusMapping = {
                1: 'intact',
                2: 'minor_damage',
                3: 'major_damage',
                4: 'major_damage',
                5: 'severely_damaged',
                6: 'destroyed',
                7: 'under_construction',
                8: 'demolished',
                99: 'intact'
            };

            function getStatusKey(status) {
                return typeof status === 'number' ? (statusMapping[status] || 'intact') : status;
            }
            console.log('getStatusKey defined for viewport loading');
        }

        // Configuration (from MapConstants)
        var MIN_ZOOM_FOR_LOADING = 15;
        var MAX_MARKERS_PER_VIEWPORT = 2000; // محسّن: زيادة من 1000 إلى 2000

        // Viewport loading state
        var viewportLoadingEnabled = true;
        var viewportLoadingDebounceTimer = null;
        var viewportLoadingDebounceDelay = 500; // ms
        var currentBuildingsLayer = null;
        var currentMarkersCluster = null;
        var isLoadingViewport = false;

        // Reuse bridge from selection JS (already initialized)
        // Don't create a new QWebChannel - use the existing 'bridge' variable
        // The selection JS (loaded before this) already created 'bridge' and 'bridgeReady'

        // Wait for bridge to be ready before enabling viewport loading
        var viewportBridgeCheckInterval = setInterval(function() {
            if (typeof bridgeReady !== 'undefined' && bridgeReady && typeof bridge !== 'undefined' && bridge) {
                clearInterval(viewportBridgeCheckInterval);
                console.log('Viewport loading: Reusing existing bridge (ready)');

                // Trigger initial viewport load after bridge is confirmed ready
                if (viewportLoadingEnabled) {
                    console.log('Triggering initial viewport load');
                    setTimeout(function() {
                        loadBuildingsForViewport();
                    }, 100);
                }
            }
        }, 50); // Check every 50ms

        // Timeout after 5 seconds
        setTimeout(function() {
            clearInterval(viewportBridgeCheckInterval);
            if (typeof bridgeReady === 'undefined' || !bridgeReady) {
                console.error('Bridge not ready after 5 seconds - viewport loading disabled');
            }
        }, 5000);

        /**
         * Load buildings for current viewport bounds.
         * Called on map moveend/zoomend events.
         *
         * - Min zoom check (don't load at low zoom levels)
         * - Max markers limit per viewport
         * - Debouncing to prevent too many requests
         */
        function loadBuildingsForViewport() {
            if (!viewportLoadingEnabled || isLoadingViewport) {
                return;
            }

            // Skip viewport loading during flyTo (prevents jitter)
            if (typeof window._isFlying !== 'undefined' && window._isFlying === true) {
                console.log('Skipping viewport load during flyTo animation (prevents jitter)');
                return;
            }

            // Min zoom check - don't load buildings when zoomed out too far
            var currentZoom = map.getZoom();
            if (currentZoom < MIN_ZOOM_FOR_LOADING) {
                console.log('Zoom level ' + currentZoom + ' < ' + MIN_ZOOM_FOR_LOADING + ', skipping building load');

                // Clear existing buildings when zoomed out too far
                if (currentBuildingsLayer) {
                    map.removeLayer(currentBuildingsLayer);
                    currentBuildingsLayer = null;
                }
                if (currentMarkersCluster) {
                    map.removeLayer(currentMarkersCluster);
                    currentMarkersCluster = null;
                }

                return;
            }

            // Get current viewport bounds
            var bounds = map.getBounds();
            var northEast = bounds.getNorthEast();
            var southWest = bounds.getSouthWest();
            var center = map.getCenter();  // إضافة center للتوافق مع ViewportBridge

            console.log('Viewport bounds:', {
                northEast: northEast,
                southWest: southWest,
                center: center,
                zoom: currentZoom,
                minZoom: MIN_ZOOM_FOR_LOADING,
                maxMarkers: MAX_MARKERS_PER_VIEWPORT
            });

            // Send bounds to Python via WebChannel
            // Use shared 'bridge' variable from selection JS
            if (typeof bridgeReady !== 'undefined' && bridgeReady && bridge && bridge.onViewportChanged) {
                isLoadingViewport = true;

                bridge.onViewportChanged(
                    northEast.lat,
                    northEast.lng,
                    southWest.lat,
                    southWest.lng,
                    currentZoom,
                    center.lat,
                    center.lng
                );

                console.log('Requesting buildings for viewport (max: ' + MAX_MARKERS_PER_VIEWPORT + ')...');
            } else if (typeof bridgeReady === 'undefined' || !bridgeReady) {
                console.warn('Bridge not ready yet, skipping viewport load');
                isLoadingViewport = false;
            } else {
                console.error('Bridge not available or missing onViewportChanged method');
                isLoadingViewport = false;
            }
        }

        /**
         * Update buildings on map with new GeoJSON data.
         * Called from Python when new viewport data is loaded.
         *
         * - Converts all geometries to Point (pin markers)
         * - Uses marker clustering
         * - Limits to MAX_MARKERS_PER_VIEWPORT
         *
         * @param {string} buildingsGeoJSON - GeoJSON FeatureCollection string
         */
        function updateBuildingsOnMap(buildingsGeoJSON) {
            try {
                console.log('Updating buildings on map with clustering...');

                // Parse GeoJSON
                var newBuildingsData = typeof buildingsGeoJSON === 'string'
                    ? JSON.parse(buildingsGeoJSON)
                    : buildingsGeoJSON;

                // Convert all Polygon/MultiPolygon to Point (centroid) for pin-only display
                if (newBuildingsData.features) {
                    newBuildingsData.features.forEach(function(f) {
                        if (f.geometry.type === 'Polygon' || f.geometry.type === 'MultiPolygon') {
                            var bounds = L.geoJSON(f).getBounds();
                            var center = bounds.getCenter();
                            f.geometry = { type: 'Point', coordinates: [center.lng, center.lat] };
                        }
                    });
                }

                console.log('  - Buildings count:', newBuildingsData.features.length);
                console.log('  - Max markers limit:', MAX_MARKERS_PER_VIEWPORT);

                // Limit to MAX_MARKERS_PER_VIEWPORT
                if (newBuildingsData.features.length > MAX_MARKERS_PER_VIEWPORT) {
                    console.warn('Too many buildings (' + newBuildingsData.features.length + '), limiting to ' + MAX_MARKERS_PER_VIEWPORT);
                    newBuildingsData.features = newBuildingsData.features.slice(0, MAX_MARKERS_PER_VIEWPORT);
                }

                // Remove existing layers if present
                if (currentBuildingsLayer) {
                    map.removeLayer(currentBuildingsLayer);
                    console.log('  - Removed old buildings layer');
                }
                if (currentMarkersCluster) {
                    map.removeLayer(currentMarkersCluster);
                    console.log('  - Removed old markers cluster');
                }

                // Create marker cluster group for points
                if (typeof L.markerClusterGroup === 'function') {
                    currentMarkersCluster = L.markerClusterGroup({
                        maxClusterRadius: 60,
                        spiderfyOnMaxZoom: true,
                        showCoverageOnHover: false,
                        zoomToBoundsOnClick: true,
                        disableClusteringAtZoom: 15,
                        chunkedLoading: true,
                        chunkInterval: 100,
                        chunkDelay: 10,
                        removeOutsideVisibleBounds: true,
                        animate: true,
                        animateAddingMarkers: false
                    });
                } else {
                    console.warn('MarkerCluster not available, using featureGroup fallback');
                    currentMarkersCluster = L.featureGroup();
                }

                // Create new buildings layer (all features are Points after conversion)
                currentBuildingsLayer = L.geoJSON(newBuildingsData, {
                    // pointToLayer for Point features
                    pointToLayer: function(feature, latlng) {
                        var status = getStatusKey(feature.properties.status || 1);
                        var color = statusColors[status] || '#0072BC';
                        var isAssigned = feature.properties.is_assigned === true;

                        var innerSvg;
                        if (isAssigned) {
                            color = '#F59E0B';
                            innerSvg = '<text x="12" y="16" text-anchor="middle" fill="#fff" font-size="10" font-weight="bold">&#10003;</text>';
                        } else {
                            innerSvg = '<circle cx="12" cy="12" r="4" fill="#fff"/>';
                        }

                        var pinIcon = L.divIcon({
                            className: 'building-pin-icon',
                            html: '<div style="position:relative;width:24px;height:36px;">' +
                                  '<svg width="24" height="36" viewBox="0 0 24 36" xmlns="http://www.w3.org/2000/svg">' +
                                  '<path d="M12 0C5.4 0 0 5.4 0 12c0 8 12 24 12 24s12-16 12-24c0-6.6-5.4-12-12-12z" ' +
                                  'fill="' + color + '" stroke="#fff" stroke-width="2"/>' +
                                  innerSvg +
                                  '</svg></div>',
                            iconSize: [24, 36],
                            iconAnchor: [12, 36],
                            popupAnchor: [0, -36]
                        });

                        return L.marker(latlng, { icon: pinIcon });
                    },

                    // onEachFeature for popups/multiselect and events
                    onEachFeature: function(feature, layer) {
                        var props = feature.properties;
                        var status = props.status || 'intact';
                        var statusLabel = statusLabels[status] || status;
                        var statusClass = 'status-' + status;
                        var geomType = props.geometry_type || 'Point';

                        // All buildings are Points — add to marker cluster
                        currentMarkersCluster.addLayer(layer);

                        // Multi-select mode: attach click handler instead of popup
                        if (window.multiselectMode && typeof window.attachMultiselectHandler === 'function') {
                            window.attachMultiselectHandler(layer);
                            return;
                        }

                        // Normal mode: build popup
                        var buildingIdDisplay = props.building_id_display || props.building_id || 'مبنى';
                        var buildingIdForApi = props.building_id;

                        var popup = '<div class="building-popup">' +
                            '<h4>' + buildingIdDisplay + ' ' +
                            '<span class="geometry-badge">' + geomType + '</span></h4>' +
                            '<p><span class="label">الحي:</span> ' + (props.neighborhood || 'غير محدد') + '</p>' +
                            '<p><span class="label">الحالة:</span> ' +
                            '<span class="status-badge ' + statusClass + '">' + statusLabel + '</span></p>' +
                            '<p><span class="label">الوحدات:</span> ' + (props.units || 0) + '</p>';

                        if (props.type) {
                            popup += '<p><span class="label">النوع:</span> ' + props.type + '</p>';
                        }

                        if (typeof window.selectBuilding === 'function' && buildingIdForApi) {
                            popup += "<button class=\\"select-building-btn\\" onclick=\\"selectBuilding(&apos;" + buildingIdForApi + "&apos;)\\\"><span style=\\"font-size:16px\\">✓</span> اختيار هذا المبنى</button>";
                        }

                        popup += '</div>';

                        layer.bindPopup(popup);

                    }
                });

                // Add marker cluster to map
                map.addLayer(currentMarkersCluster);

                isLoadingViewport = false;
                var totalCount = currentMarkersCluster.getLayers().length;
                console.log('Buildings updated: ' + totalCount);
                if (typeof window.updateBuildingCount === 'function') {
                    window.updateBuildingCount(totalCount);
                }

            } catch (error) {
                console.error('Error updating buildings:', error);
                isLoadingViewport = false;
            }
        }

        // Expose function to window for Python to call
        window.updateBuildingsOnMap = updateBuildingsOnMap;

        /**
         * Debounced viewport change handler.
         * Prevents too many requests when user pans/zooms rapidly.
         */
        function onViewportChanged() {
            // Clear existing timer
            if (viewportLoadingDebounceTimer) {
                clearTimeout(viewportLoadingDebounceTimer);
            }

            // Set new timer
            viewportLoadingDebounceTimer = setTimeout(function() {
                loadBuildingsForViewport();
            }, viewportLoadingDebounceDelay);
        }

        // Attach viewport change listeners to map
        if (viewportLoadingEnabled) {
            map.on('moveend', onViewportChanged);
            map.on('zoomend', onViewportChanged);

            console.log('Viewport-based loading enabled');
            console.log('   - Debounce delay:', viewportLoadingDebounceDelay, 'ms');

            // Load initial viewport (optional - can skip if initial buildings already loaded)
            // setTimeout(function() {
            //     loadBuildingsForViewport();
            // }, 1000);
        }
'''

# Export template
__all__ = ['VIEWPORT_LOADING_JS_TEMPLATE']
