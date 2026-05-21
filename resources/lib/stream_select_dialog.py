"""Optional WindowXML stream selection dialog."""
from __future__ import annotations

import xbmcgui


class StreamSelectDialog(xbmcgui.WindowXMLDialog):
    """Custom dialog listing streams with a heading."""

    def __init__(self, xml_filename: str, addon_path: str, streams: list, title: str):
        super().__init__(xml_filename, addon_path, "Default", "1080i")
        self.streams = streams
        self.title = title
        self.selected_index = -1

    def onInit(self) -> None:
        try:
            self.getControl(1).setLabel(self.title)
        except RuntimeError:
            pass
        try:
            listing = self.getControl(100)
            labels = [s.get("display", s.get("name", "")) for s in self.streams]
            listing.addItems(labels)
        except RuntimeError:
            pass

    def onClick(self, control_id: int) -> None:
        if control_id == 100:
            try:
                listing = self.getControl(100)
                self.selected_index = listing.getSelectedPosition()
                self.close()
            except RuntimeError:
                pass
        elif control_id in (200, 201):
            self.selected_index = -1
            self.close()

    def get_selection(self):
        if 0 <= self.selected_index < len(self.streams):
            return self.streams[self.selected_index].get("stream")
        return None


def show_xml_stream_picker(addon, streams: list, title: str, build_display_fn):
    """Try XML dialog; return selected stream dict or None."""
    display_streams = []
    for stream in streams:
        display_streams.append(
            {"stream": stream, "display": build_display_fn(stream), "name": stream.get("name")}
        )
    xml_path = addon.getAddonInfo("path")
    try:
        dialog = StreamSelectDialog("DialogStreamSelect.xml", xml_path, display_streams, title)
        dialog.doModal()
        selected = dialog.get_selection()
        del dialog
        return selected
    except Exception:
        return None
