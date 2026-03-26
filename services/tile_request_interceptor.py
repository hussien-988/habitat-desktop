# -*- coding: utf-8 -*-
"""
Tile Request Interceptor — adds User-Agent and Referer headers
to external tile server requests via QWebEngine.
"""

from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor


class TileRequestInterceptor(QWebEngineUrlRequestInterceptor):
    """Intercepts outgoing tile requests to add required HTTP headers."""

    USER_AGENT = "TRRCMS-Desktop/1.0 (UN-Habitat Syria)"
    REFERER = "https://trrcms.unhabitat.org"

    def interceptRequest(self, info):
        url = info.requestUrl().toString()
        if self._is_external_tile_request(url):
            info.setHttpHeader(b"User-Agent", self.USER_AGENT.encode())
            info.setHttpHeader(b"Referer", self.REFERER.encode())

    @staticmethod
    def _is_external_tile_request(url):
        if "127.0.0.1" in url or "localhost" in url:
            return False
        return "tile" in url or "/z/" in url or ".png" in url or ".pbf" in url
