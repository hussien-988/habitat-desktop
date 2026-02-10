# -*- coding: utf-8 -*-
"""Template for Leaflet drawing JavaScript - يتم استيراده من leaflet_html_generator.py"""

DRAWING_JS_TEMPLATE = """
        // ✅ Drawing JS: Initialize tools immediately, bridge will be available when needed
        console.log('🔧 Drawing JS: Initializing drawing tools...');
        console.log('   window.bridge:', window.bridge);
        console.log('   window.bridgeReady:', window.bridgeReady);

        // Queue for pending geometry (before bridge is ready)
        var pendingGeometry = null;
        var bridgeCheckAttempts = 0;
        var maxBridgeCheckAttempts = 60; // Check for up to 30 seconds

        // Register callback to be called when bridge is ready
        if (typeof window.onBridgeReady !== 'function') {
            window.onBridgeReady = function() {
                console.log('🎉 Drawing JS: Bridge is now ready (via callback)!');
                // Send any pending geometry
                if (pendingGeometry) {
                    console.log('📤 Sending pending geometry...');
                    sendGeometryToPython(pendingGeometry.geomType, pendingGeometry.wkt);
                    pendingGeometry = null;
                }
            };
        }

        // ✅ AGGRESSIVE POLLING: Check for bridge every 500ms
        // This ensures we catch the bridge even if callback doesn't fire
        var bridgePollingInterval = setInterval(function() {
            bridgeCheckAttempts++;

            if (window.bridge && typeof window.bridge.onGeometryDrawn === 'function') {
                // Bridge found!
                clearInterval(bridgePollingInterval);
                console.log('🎉 Drawing JS: Bridge found via polling (attempt ' + bridgeCheckAttempts + ')!');

                // Process any pending geometry
                if (pendingGeometry) {
                    console.log('📤 Sending pending geometry from polling...');
                    sendGeometryToPython(pendingGeometry.geomType, pendingGeometry.wkt);
                    pendingGeometry = null;
                }
            } else if (bridgeCheckAttempts >= maxBridgeCheckAttempts) {
                clearInterval(bridgePollingInterval);
                console.error('❌ Bridge not found after ' + (maxBridgeCheckAttempts * 0.5) + ' seconds of polling');
                console.log('   This is a critical error - QWebChannel failed to initialize');
            }
        }, 500); // Check every 500ms

        // Drawing layer for new shapes
        var drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);

        // Helper function to send geometry to Python (with retry logic + queue)
        // Defined globally so it can be used by both Leaflet.draw and fallback mode
        function sendGeometryToPython(geomType, wkt, retryCount) {
            retryCount = retryCount || 0;
            var maxRetries = 20;  // Increase retries to 20 (10 seconds total)

            // Always use window.bridge (set by Selection JS)
            if (window.bridge && typeof window.bridge.onGeometryDrawn === 'function') {
                try {
                    console.log('📡 Sending to Python via bridge.onGeometryDrawn');
                    console.log('   geomType:', geomType);
                    console.log('   wkt:', wkt ? wkt.substring(0, 100) + '...' : 'null');
                    window.bridge.onGeometryDrawn(geomType, wkt);
                    console.log('✅ Successfully sent geometry to Python');
                    // Clear any pending geometry
                    pendingGeometry = null;
                } catch (error) {
                    console.error('❌ Error sending geometry:', error);
                    // Retry on error
                    if (retryCount < maxRetries) {
                        console.warn('   Retrying in 500ms...');
                        setTimeout(function() {
                            sendGeometryToPython(geomType, wkt, retryCount + 1);
                        }, 500);
                    }
                }
            } else {
                // Bridge not ready yet - wait and retry, or queue it
                if (retryCount < maxRetries) {
                    console.warn('⏳ Bridge not ready (attempt ' + (retryCount + 1) + '/' + maxRetries + '), waiting 500ms...');
                    setTimeout(function() {
                        sendGeometryToPython(geomType, wkt, retryCount + 1);
                    }, 500);
                } else {
                    // Max retries reached - queue it for later
                    console.warn('⏰ Bridge not ready after ' + (maxRetries * 500) + 'ms, queuing geometry...');
                    console.log('   Geometry will be sent when bridge is ready');
                    pendingGeometry = {geomType: geomType, wkt: wkt};
                }
            }
        }

        // Drawing controls
        console.log('Checking for Leaflet.draw library...');
        console.log('L.Control.Draw:', typeof L.Control.Draw);
        console.log('L.Draw:', typeof L.Draw);
        console.log('Drawing mode: __DRAWING_MODE__');

        if (typeof L.Control.Draw !== 'undefined') {
            console.log('✅ Leaflet.draw library loaded successfully');

            // تحديد الأدوات المفعلة بناءً على الوضع
            var enableMarker = __ENABLE_MARKER__;
            var enablePolygon = __ENABLE_POLYGON__;

            var drawControl = new L.Control.Draw({
                position: 'topright',
                draw: {
                    polyline: false,
                    rectangle: false,
                    circle: false,
                    circlemarker: false,
                    marker: enableMarker ? {
                        icon: L.icon({
                            iconUrl: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjUiIGhlaWdodD0iNDEiIHZpZXdCb3g9IjAgMCAyNSA0MSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNMTIuNSAwQzUuNiAwIDAgNS42IDAgMTIuNWMwIDEuOC40IDMuNSAxLjIgNS4xTDEyLjUgNDEgMjMuOCAxNy42Yy44LTEuNiAxLjItMy4zIDEuMi01LjFDMjUgNS42IDE5LjQgMCAxMi41IDB6IiBmaWxsPSIjMDA3MkJDIi8+PGNpcmNsZSBjeD0iMTIuNSIgY3k9IjEyLjUiIHI9IjUiIGZpbGw9IndoaXRlIi8+PC9zdmc+',
                            iconSize: [25, 41],
                            iconAnchor: [12, 41]
                        }),
                        repeatMode: false  // لا تستمر في وضع الرسم بعد إضافة نقطة
                    } : false,
                    polygon: enablePolygon ? {
                        allowIntersection: false,
                        showArea: true,
                        drawError: {
                            color: '#e1e100',
                            message: '<strong>لا يمكن رسم مضلع متقاطع!</strong>'
                        },
                        shapeOptions: {
                            color: '#4A90E2',
                            weight: 2,
                            fillColor: '#4A90E2',
                            fillOpacity: 0.45
                        },
                        repeatMode: false,  // لا تستمر في وضع الرسم بعد إكمال المضلع
                        showLength: true    // عرض طول الحافة أثناء الرسم
                    } : false
                },
                edit: {
                    featureGroup: drawnItems,
                    remove: true
                }
            });
            map.addControl(drawControl);

            // إضافة مربع تعليمات للرسم
            var drawingInstructions = L.control({position: 'topright'});
            drawingInstructions.onAdd = function(map) {
                var div = L.DomUtil.create('div', 'drawing-instructions-box');
                div.style.cssText = 'background: white; padding: 12px 16px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.25); font-size: 13px; direction: rtl; max-width: 280px; display: none; margin-top: 10px;';
                div.id = 'drawingInstructions';
                return div;
            };
            drawingInstructions.addTo(map);

            // دالة لتحديث التعليمات حسب نوع الرسم
            function updateDrawingInstructions(layerType) {
                var instructionsBox = document.getElementById('drawingInstructions');
                if (!instructionsBox) return;

                if (layerType === 'polygon') {
                    instructionsBox.innerHTML = '<div style="font-weight: 600; color: #0072BC; margin-bottom: 6px;">📐 تعليمات رسم المضلع:</div>' +
                                               '<div style="color: #333; line-height: 1.6; font-size: 12px;">' +
                                               '1️⃣ اضغط على الخريطة لإضافة نقاط<br>' +
                                               '2️⃣ <strong style="color:#28a745">اضغط مرتين متتاليتين</strong> لإنهاء الرسم (أسهل طريقة!)<br>' +
                                               '3️⃣ أو اضغط على النقطة الأولى لإغلاق المضلع<br>' +
                                               '4️⃣ أو اضغط زر <strong style="color:#0072BC">FINISH</strong> في الأعلى<br>' +
                                               '❌ اضغط ESC للإلغاء</div>';
                } else if (layerType === 'marker') {
                    instructionsBox.innerHTML = '<div style="font-weight: 600; color: #0072BC; margin-bottom: 6px;">📍 تعليمات إضافة نقطة:</div>' +
                                               '<div style="color: #333; line-height: 1.6; font-size: 12px;">' +
                                               '✓ اضغط على الخريطة لإضافة نقطة<br>' +
                                               '❌ اضغط ESC للإلغاء</div>';
                }
            }

            // إظهار/إخفاء التعليمات عند بدء/إنهاء الرسم
            map.on(L.Draw.Event.DRAWSTART, function(e) {
                var instructionsBox = document.getElementById('drawingInstructions');
                if (instructionsBox) {
                    updateDrawingInstructions(e.layerType);
                    instructionsBox.style.display = 'block';
                }
            });

            map.on(L.Draw.Event.DRAWSTOP, function(e) {
                var instructionsBox = document.getElementById('drawingInstructions');
                if (instructionsBox) {
                    instructionsBox.style.display = 'none';
                }
            });

            // Handle drawing created
            map.on(L.Draw.Event.CREATED, function(e) {
                var type = e.layerType;
                var layer = e.layer;

                // إزالة جميع الأشكال السابقة (نريد رسم واحد فقط في كل مرة)
                drawnItems.clearLayers();

                // إضافة الشكل الجديد
                drawnItems.addLayer(layer);

                // Get geometry and convert to WKT
                var geomType = null;
                var wkt = null;

                if (type === 'marker') {
                    var latlng = layer.getLatLng();
                    geomType = 'Point';
                    wkt = 'POINT(' + latlng.lng + ' ' + latlng.lat + ')';

                    // ✨ تحسين UX: جعل النقطة draggable مع popup للحذف
                    layer.dragging.enable();

                    // إضافة popup مع زر حذف
                    var popupContent = '<div style="text-align: center; direction: rtl; padding: 4px;">' +
                                      '<button onclick="deleteCurrentMarker()" style="background: #dc3545; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 500; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">🗑️ حذف النقطة</button>' +
                                      '<div style="margin-top: 8px; font-size: 11px; color: #666;">💡 يمكنك سحب النقطة لتغيير موقعها</div>' +
                                      '</div>';
                    layer.bindPopup(popupContent);

                    // تحديث الموقع عند السحب
                    layer.on('dragend', function(e) {
                        var newLatLng = e.target.getLatLng();
                        var newWkt = 'POINT(' + newLatLng.lng + ' ' + newLatLng.lat + ')';
                        console.log('✅ Marker dragged to new position:', newWkt);

                        sendGeometryToPython('Point', newWkt);
                    });

                } else if (type === 'polygon') {
                    var latlngs = layer.getLatLngs()[0];
                    var coords = latlngs.map(function(ll) {
                        return ll.lng + ' ' + ll.lat;
                    }).join(', ');
                    // Close the polygon
                    var firstPoint = latlngs[0];
                    coords += ', ' + firstPoint.lng + ' ' + firstPoint.lat;
                    geomType = 'Polygon';
                    wkt = 'POLYGON((' + coords + '))';
                }

                console.log('✅ Shape created:', geomType, wkt);

                // Send to Python via QWebChannel (wait for bridge if not ready)
                sendGeometryToPython(geomType, wkt);
            });

            // دالة لحذف النقطة الحالية (يتم استدعاؤها من popup)
            window.deleteCurrentMarker = function() {
                drawnItems.clearLayers();
                console.log('✅ Marker deleted by user');

                // إخطار Python بأن الهندسة تم حذفها
                sendGeometryToPython(null, null);
            };

            // Handle editing
            map.on(L.Draw.Event.EDITED, function(e) {
                var layers = e.layers;
                console.log('Shapes edited:', layers.getLayers().length);
            });

            // Handle deletion
            map.on(L.Draw.Event.DELETED, function(e) {
                var layers = e.layers;
                console.log('Shapes deleted:', layers.getLayers().length);
            });
        } else {
            console.warn('⚠️ Leaflet.draw library not loaded. Using fallback: click to add marker');

            // Fallback: Simple click-to-add marker mode
            var currentMarker = null;

            map.on('click', function(e) {
                // Remove previous marker
                if (currentMarker) {
                    map.removeLayer(currentMarker);
                }

                // Add new marker (draggable)
                currentMarker = L.marker(e.latlng, {
                    icon: L.icon({
                        iconUrl: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjUiIGhlaWdodD0iNDEiIHZpZXdCb3g9IjAgMCAyNSA0MSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNMTIuNSAwQzUuNiAwIDAgNS42IDAgMTIuNWMwIDEuOC40IDMuNSAxLjIgNS4xTDEyLjUgNDEgMjMuOCAxNy42Yy44LTEuNiAxLjItMy4zIDEuMi01LjFDMjUgNS42IDE5LjQgMCAxMi41IDB6IiBmaWxsPSIjRkYwMDAwIi8+PGNpcmNsZSBjeD0iMTIuNSIgY3k9IjEyLjUiIHI9IjUiIGZpbGw9IndoaXRlIi8+PC9zdmc+',
                        iconSize: [25, 41],
                        iconAnchor: [12, 41]
                    }),
                    draggable: true  // ✨ تحسين UX: draggable في fallback mode أيضاً
                }).addTo(map);

                drawnItems.addLayer(currentMarker);

                // إضافة popup مع زر حذف
                var popupContent = '<div style="text-align: center; direction: rtl; padding: 4px;">' +
                                  '<button onclick="deleteCurrentMarkerFallback()" style="background: #dc3545; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 500; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">🗑️ حذف النقطة</button>' +
                                  '<div style="margin-top: 8px; font-size: 11px; color: #666;">💡 يمكنك سحب النقطة لتغيير موقعها</div>' +
                                  '</div>';
                currentMarker.bindPopup(popupContent);

                // تحديث الموقع عند السحب
                currentMarker.on('dragend', function(e) {
                    var newLatLng = e.target.getLatLng();
                    var newWkt = 'POINT(' + newLatLng.lng + ' ' + newLatLng.lat + ')';
                    console.log('✅ Marker dragged to new position (fallback):', newWkt);

                    sendGeometryToPython('Point', newWkt);
                });

                // Create WKT
                var geomType = 'Point';
                var wkt = 'POINT(' + e.latlng.lng + ' ' + e.latlng.lat + ')';

                console.log('✅ Point created (fallback mode):', geomType, wkt);

                // Send to Python via QWebChannel
                sendGeometryToPython(geomType, wkt);
            });

            // دالة لحذف النقطة في fallback mode
            window.deleteCurrentMarkerFallback = function() {
                if (currentMarker) {
                    map.removeLayer(currentMarker);
                    currentMarker = null;
                    console.log('✅ Marker deleted by user (fallback)');

                    // إخطار Python بأن الهندسة تم حذفها
                    sendGeometryToPython(null, null);
                }
            };

            // Add instructions
            var instructions = L.control({position: 'topright'});
            instructions.onAdd = function(map) {
                var div = L.DomUtil.create('div', 'drawing-instructions');
                div.innerHTML = '<div style="background: white; padding: 10px; border-radius: 6px; box-shadow: 0 2px 6px rgba(0,0,0,0.2); font-size: 12px; direction: rtl;">📍 اضغط على الخريطة لإضافة نقطة</div>';
                return div;
            };
            instructions.addTo(map);
        }
"""
