# Restart Inkscape

An Inkscape extension that closes Inkscape and opens it again with the file that was active. Handy after changing extensions, which Inkscape only loads at startup.

It first saves the document in every open Inkscape window (Inkscape's own Save, as with Ctrl+S), then closes Inkscape with its own Quit. A new document that has never been saved gets Inkscape's Save As dialog; if you leave it unsaved, Quit asks about it, and Cancel there keeps Inkscape open.

Only the active document is reopened. An unsaved new document has no file, so Inkscape reopens empty.

## Menu

Extensions > Map's Edge Tools > General > Inkscape > Restart Inkscape

## Notes

Made for the Flatpak build of Inkscape: the new Inkscape starts inside the same sandbox, since the sandbox cannot start programs outside itself. Tested with Inkscape 1.4.
