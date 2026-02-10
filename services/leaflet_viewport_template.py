# -*- coding: utf-8 -*-
"""
Leaflet Viewport Loading Template
==================================

JavaScript template for viewport-based building loading.
Implements industry best practices for handling millions of buildings.

Best Practices Applied:
- Viewport-based loading (only load visible buildings)
- Debouncing for performance (prevent too many requests)
- Smart caching on client side
- Dynamic marker updates without full page reload

References:
- https://leafletjs.com/reference.html#map-event
- https://developers.google.com/maps/documentation/javascript/examples/layer-data-dynamic
"""

VIEWPORT_LOADING_JS_TEMPLATE = '''
        // =========================================================
        // Viewport-Based Loading (Professional Best Practice)
        // =========================================================

        // ✅ CRITICAL: Define getStatusKey if not already defined (for viewport loading)
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
            console.log('✅ getStatusKey defined for viewport loading');
        }

        // Professional Configuration (✅ محدّث من MapConstants)
        var MIN_ZOOM_FOR_LOADING = 12;      // Don't load buildings below this zoom (performance)
        var MAX_MARKERS_PER_VIEWPORT = 2000; // ✅ محسّن: زيادة من 1000 إلى 2000

        // Viewport loading state
        var viewportLoadingEnabled = true;
        var viewportLoadingDebounceTimer = null;
        var viewportLoadingDebounceDelay = 500; // ms
        var currentBuildingsLayer = null;
        var currentMarkersCluster = null;
        var isLoadingViewport = false;

        // ✅ IMPORTANT: Reuse bridge from selection JS (already initialized)
        // Don't create a new QWebChannel - use the existing 'bridge' variable
        // The selection JS (loaded before this) already created 'bridge' and 'bridgeReady'

        // Wait for bridge to be ready before enabling viewport loading
        var viewportBridgeCheckInterval = setInterval(function() {
            if (typeof bridgeReady !== 'undefined' && bridgeReady && typeof bridge !== 'undefined' && bridge) {
                clearInterval(viewportBridgeCheckInterval);
                console.log('✅ Viewport loading: Reusing existing bridge (ready)');

                // Trigger initial viewport load after bridge is confirmed ready
                if (viewportLoadingEnabled) {
                    console.log('🔄 Triggering initial viewport load');
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
                console.error('❌ Bridge not ready after 5 seconds - viewport loading disabled');
            }
        }, 5000);

        /**
         * Load buildings for current viewport bounds.
         * Called on map moveend/zoomend events.
         *
         * Professional Best Practices:
         * - Min zoom check (don't load at low zoom levels)
         * - Max markers limit per viewport
         * - Debouncing to prevent too many requests
         */
        function loadBuildingsForViewport() {
            if (!viewportLoadingEnabled || isLoadingViewport) {
                return;
            }

            // PROFESSIONAL FIX: Skip viewport loading during flyTo (prevents jitter!)
            if (typeof window._isFlying !== 'undefined' && window._isFlying === true) {
                console.log('⏸️ Skipping viewport load during flyTo animation (prevents jitter)');
                return;
            }

            // Professional: Min zoom check - don't load buildings when zoomed out too far
            var currentZoom = map.getZoom();
            if (currentZoom < MIN_ZOOM_FOR_LOADING) {
                console.log('⚠️ Zoom level ' + currentZoom + ' < ' + MIN_ZOOM_FOR_LOADING + ', skipping building load');

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
            var center = map.getCenter();  // ✅ إضافة center للتوافق مع ViewportBridge

            console.log('📍 Viewport bounds:', {
                northEast: northEast,
                southWest: southWest,
                center: center,  // ✅ جديد
                zoom: currentZoom,
                minZoom: MIN_ZOOM_FOR_LOADING,
                maxMarkers: MAX_MARKERS_PER_VIEWPORT
            });

            // Send bounds to Python via WebChannel
            // ✅ Use shared 'bridge' variable from selection JS
            if (typeof bridgeReady !== 'undefined' && bridgeReady && bridge && bridge.onViewportChanged) {
                isLoadingViewport = true;

                bridge.onViewportChanged(
                    northEast.lat,
                    northEast.lng,
                    southWest.lat,
                    southWest.lng,
                    currentZoom,
                    center.lat,     // ✅ 7 parameters
                    center.lng
                );

                console.log('📡 Requesting buildings for viewport (max: ' + MAX_MARKERS_PER_VIEWPORT + ')...');
            } else if (typeof bridgeReady === 'undefined' || !bridgeReady) {
                console.warn('⚠️ Bridge not ready yet, skipping viewport load');
                isLoadingViewport = false;
            } else {
                console.error('❌ Bridge not available or missing onViewportChanged method');
                isLoadingViewport = false;
            }
        }

        /**
         * Update buildings on map with new GeoJSON data.
         * Called from Python when new viewport data is loaded.
         *
         * Professional Best Practices:
         * - Uses marker clustering for points
         * - Separates points and polygons
         * - Limits to MAX_MARKERS_PER_VIEWPORT
         *
         * @param {string} buildingsGeoJSON - GeoJSON FeatureCollection string
         */
        function updateBuildingsOnMap(buildingsGeoJSON) {
            try {
                console.log('🔄 Updating buildings on map with clustering...');

                // Parse GeoJSON
                var newBuildingsData = typeof buildingsGeoJSON === 'string'
                    ? JSON.parse(buildingsGeoJSON)
                    : buildingsGeoJSON;

                console.log('  - New buildings count:', newBuildingsData.features.length);
                console.log('  - Max markers limit:', MAX_MARKERS_PER_VIEWPORT);

                // Professional: Limit to MAX_MARKERS_PER_VIEWPORT
                if (newBuildingsData.features.length > MAX_MARKERS_PER_VIEWPORT) {
                    console.warn('⚠️ Too many buildings (' + newBuildingsData.features.length + '), limiting to ' + MAX_MARKERS_PER_VIEWPORT);
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
                // ✅ محدّث: نفس إعدادات المرحلة 1 (محسّنة)
                currentMarkersCluster = L.markerClusterGroup({
                    maxClusterRadius: 60,              // ✅ محسّن: 80 → 60
                    spiderfyOnMaxZoom: true,
                    showCoverageOnHover: false,
                    zoomToBoundsOnClick: true,
                    disableClusteringAtZoom: 15,      // ✅ محسّن: 17 → 15
                    chunkedLoading: true,
                    chunkInterval: 100,                // ✅ محسّن: 200 → 100ms
                    chunkDelay: 25,                    // ✅ محسّن: 50 → 25ms
                    removeOutsideVisibleBounds: true,  // ✅ جديد
                    animate: true,
                    animateAddingMarkers: false        // ✅ جديد
                });

                // Separate polygons layer
                var polygonsGroup = L.featureGroup();

                // Create new buildings layer (reuse same style/pointToLayer logic)
                currentBuildingsLayer = L.geoJSON(newBuildingsData, {
                    // Style function for Polygon/MultiPolygon features
                    style: function(feature) {
                        var status = getStatusKey(feature.properties.status || 1);  // ✅ FIX: استخدام getStatusKey
                        var color = statusColors[status] || '#0072BC';

                        return {
                            color: '#fff',
                            weight: 2,
                            fillColor: color,
                            fillOpacity: 0.6,
                            opacity: 1,
                            className: 'building-polygon'
                        };
                    },

                    // pointToLayer for Point features
                    pointToLayer: function(feature, latlng) {
                        var status = getStatusKey(feature.properties.status || 1);
                        var color = statusColors[status] || '#0072BC';

                        var pinIcon = L.divIcon({
                            className: 'building-pin-icon',
                            html: '<div style="position: relative; width: 24px; height: 36px;">' +
                                  '<svg width="24" height="36" viewBox="0 0 24 36" xmlns="http://www.w3.org/2000/svg">' +
                                  '<path d="M12 0C5.4 0 0 5.4 0 12c0 8 12 24 12 24s12-16 12-24c0-6.6-5.4-12-12-12z" ' +
                                  'fill="' + color + '" stroke="#fff" stroke-width="2"/>' +
                                  '<circle cx="12" cy="12" r="4" fill="#fff"/>' +
                                  '</svg></div>',
                            iconSize: [24, 36],
                            iconAnchor: [12, 36],
                            popupAnchor: [0, -36]
                        });

                        return L.marker(latlng, { icon: pinIcon });
                    },

                    // onEachFeature for popups and events
                    onEachFeature: function(feature, layer) {
                        var props = feature.properties;
                        var status = props.status || 'intact';
                        var statusLabel = statusLabels[status] || status;
                        var statusClass = 'status-' + status;
                        var geomType = props.geometry_type || 'Point';

                        // ✅ Use building_id_display (with dashes) for UI, building_id (no dashes) for API
                        var buildingIdDisplay = props.building_id_display || props.building_id || 'مبنى';
                        var buildingIdForApi = props.building_id;  // ✅ NO dashes for API

                        // Build popup content
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

                        // Add selection button if selectBuilding function exists (selection mode)
                        // ✅ Use building_id without dashes for API call
                        if (typeof window.selectBuilding === 'function' && buildingIdForApi) {
                            popup += "<button class=\\"select-building-btn\\" onclick=\\"selectBuilding(&apos;" + buildingIdForApi + "&apos;)\\\"><span style=\\"font-size:16px\\">✓</span> اختيار هذا المبنى</button>";
                        }

                        popup += '</div>';

                        layer.bindPopup(popup);

                        // Add to appropriate layer (points to cluster, polygons to group)
                        if (geomType === 'Point') {
                            currentMarkersCluster.addLayer(layer);
                        } else {
                            polygonsGroup.addLayer(layer);
                        }

                        // Highlight on hover (polygons only)
                        if (geomType !== 'Point') {
                            layer.on('mouseover', function(e) {
                                this.setStyle({
                                    fillOpacity: 0.8,
                                    weight: 3
                                });
                            });

                            layer.on('mouseout', function(e) {
                                currentBuildingsLayer.resetStyle(this);
                            });
                        }
                    }
                });

                // Add layers to map
                map.addLayer(currentMarkersCluster);  // Clustered points
                polygonsGroup.addTo(map);              // Polygons (no clustering)

                isLoadingViewport = false;
                console.log('✅ Buildings updated successfully with clustering');
                console.log('   - Markers in cluster:', currentMarkersCluster.getLayers().length);
                console.log('   - Polygons on map:', polygonsGroup.getLayers().length);

            } catch (error) {
                console.error('❌ Error updating buildings:', error);
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

            console.log('✅ Viewport-based loading enabled');
            console.log('   - Debounce delay:', viewportLoadingDebounceDelay, 'ms');

            // Load initial viewport (optional - can skip if initial buildings already loaded)
            // setTimeout(function() {
            //     loadBuildingsForViewport();
            // }, 1000);
        }
'''

# Export template
__all__ = ['VIEWPORT_LOADING_JS_TEMPLATE']
