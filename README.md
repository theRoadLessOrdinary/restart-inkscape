# Restart Inkscape

An Inkscape extension that closes Inkscape and opens it again with the file that was active. Handy after changing extensions, which Inkscape only loads at startup.

Inkscape is closed with its own Quit, so it still asks about unsaved changes. If you choose Cancel there, Inkscape stays open and nothing else happens.

Only the active document is reopened. An unsaved new document has no file, so Inkscape reopens empty.

## Menu

Extensions > Map's Edge Tools > General > Inkscape > Restart Inkscape

## Notes

Made for the Flatpak build of Inkscape: the new Inkscape starts inside the same sandbox, since the sandbox cannot start programs outside itself. Tested with Inkscape 1.4.
