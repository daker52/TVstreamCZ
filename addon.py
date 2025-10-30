# -*- coding: utf-8 -*-
"""Entry point for the TVStreamCZ Kodi add-on."""

from resources.lib.plugin import Plugin


def run():
    """Instantiate and execute the plugin router."""
    Plugin().run()


if __name__ == "__main__":
    run()
