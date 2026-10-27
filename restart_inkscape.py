#!/usr/bin/env python3
"""
Restart Inkscape

Closes Inkscape and opens it again with the file that was active, for
example to load changed extensions.

Every open window's document is saved first (Inkscape's own Save, as with
Ctrl+S), then Inkscape is closed with its own Quit. A new document that has
never been saved gets Inkscape's Save As dialog; if it is still unsaved,
Quit asks about it, and Cancel there stops the restart. A small helper, started
detached, waits for this script to finish, asks Inkscape to quit, waits for
it to close (up to WAIT_FOR_EXIT seconds), then starts Inkscape again with
the file. Only the active document is reopened. An unsaved new document has
no file, so Inkscape reopens empty.

Inkscape runs as a Flatpak here, and the sandbox cannot start programs
outside itself, so the new Inkscape starts inside the same sandbox.
"""
import os
import signal
import sys
import tempfile
import time
import warnings

import inkex

DBUS_BASE = 'org.inkscape.Inkscape'
WAIT_FOR_EXIT = 600     # seconds to wait for Inkscape to close
# Set by Inkscape for extension scripts; not wanted in the new Inkscape.
EXTENSION_ENV = ('DOCUMENT_PATH', 'SELF_CALL')
# The waiting helper's pid. A newer restart replaces an older helper (one
# still waiting because its quit was cancelled), so Inkscape opens only once.
HELPER_PID_PATH = os.path.join(tempfile.gettempdir(), 'restart_inkscape_helper.pid')


def _proc_stat(pid):
    """(name, parent pid) of a process, from /proc, or None."""
    try:
        with open(f'/proc/{pid}/stat') as f:
            data = f.read()
    except OSError:
        return None
    name = data[data.index('(') + 1:data.rindex(')')]
    return name, int(data[data.rindex(')') + 2:].split()[1])


def find_inkscape_pid():
    """The Inkscape that ran this script: walk up the ancestors (extensions
    are not direct children of Inkscape), then fall back to the
    lowest-numbered inkscape process (same as the Tool Panel)."""
    pid = os.getppid()
    while pid > 1:
        stat = _proc_stat(pid)
        if stat is None:
            break
        if stat[0].startswith('inkscape'):
            return pid
        pid = stat[1]
    found = []
    for entry in os.listdir('/proc'):
        if entry.isdigit():
            stat = _proc_stat(int(entry))
            if stat and stat[0].startswith('inkscape'):
                found.append(int(entry))
    return min(found) if found else None


def app_id_tag(pid):
    """The --app-id-tag Inkscape was started with, or None."""
    try:
        with open(f'/proc/{pid}/cmdline', 'rb') as f:
            args = f.read().decode('utf-8', 'replace').split('\0')
    except OSError:
        return None
    for i, arg in enumerate(args):
        if arg.startswith('--app-id-tag='):
            return arg.split('=', 1)[1]
        if arg == '--app-id-tag' and i + 1 < len(args):
            return args[i + 1]
    return None


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def save_all(conn, name):
    """Run Inkscape's Save (win.document-save) in every open window."""
    from gi.repository import Gio, GLib
    base = '/' + name.replace('.', '/') + '/window'
    try:
        xml = conn.call_sync(name, base, 'org.freedesktop.DBus.Introspectable', 'Introspect',
                             None, GLib.VariantType('(s)'), Gio.DBusCallFlags.NONE, 5000, None)[0]
    except Exception:
        return
    import re
    for node in re.findall(r'<node name="(\d+)"', xml):
        try:
            conn.call_sync(name, f'{base}/{node}', 'org.gtk.Actions', 'Activate',
                           GLib.Variant('(sava{sv})', ('document-save', [], {})),
                           None, Gio.DBusCallFlags.NONE, -1, None)
        except Exception:
            pass



def helper(script_pid, inkscape_pid, tag, path):
    """Runs detached: quit Inkscape, wait, start it again."""
    try:
        with open(HELPER_PID_PATH, 'w') as f:
            f.write(str(os.getpid()))
    except OSError:
        pass
    while alive(script_pid):
        time.sleep(0.1)
    time.sleep(1.5)   # let Inkscape finish with this extension run

    from gi.repository import Gio, GLib
    name = f'{DBUS_BASE}.{tag}' if tag else DBUS_BASE
    try:
        conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        save_all(conn, name)
        conn.call_sync(name, '/' + name.replace('.', '/'), 'org.gtk.Actions', 'Activate',
                       GLib.Variant('(sava{sv})', ('quit', [], {})),
                       None, Gio.DBusCallFlags.NONE, -1, None)
    except Exception:
        pass   # Inkscape may close before it answers

    deadline = time.time() + WAIT_FOR_EXIT
    while alive(inkscape_pid):
        if time.time() > deadline:
            return   # quit was cancelled; leave Inkscape as it is
        time.sleep(0.2)

    try:
        with open(HELPER_PID_PATH) as f:
            if f.read().strip() != str(os.getpid()):
                return   # a newer restart took over
        os.remove(HELPER_PID_PATH)
    except OSError:
        pass

    argv = ['inkscape']
    if tag:
        argv.append(f'--app-id-tag={tag}')
    if path and os.path.exists(path):
        argv.append(path)
    env = {k: v for k, v in os.environ.items() if k not in EXTENSION_ENV}
    os.execvpe('inkscape', argv, env)


def spawn_detached(fn, *args):
    """Run fn(*args) in a fully detached grandchild (double fork)."""
    # Python warns about fork() in a multi-threaded process; Inkscape would
    # show that in a dialog, which holds up the restart.
    warnings.simplefilter('ignore')
    pid = os.fork()
    if pid == 0:
        try:
            os.setsid()
            devnull = os.open(os.devnull, os.O_RDWR)
            for fd in (0, 1, 2):
                os.dup2(devnull, fd)
            if os.fork() == 0:
                try:
                    fn(*args)
                finally:
                    os._exit(0)
        finally:
            os._exit(0)
    os.waitpid(pid, 0)


def stop_waiting_helper():
    """Stop a helper from an earlier restart that is still waiting."""
    try:
        with open(HELPER_PID_PATH) as f:
            pid = int(f.read().strip())
        with open(f'/proc/{pid}/cmdline', 'rb') as f:
            if b'restart_inkscape' not in f.read():
                return
        os.kill(pid, signal.SIGTERM)
    except (OSError, ValueError):
        pass


class RestartInkscape(inkex.EffectExtension):

    def effect(self):
        stop_waiting_helper()
        inkscape_pid = find_inkscape_pid()
        if inkscape_pid is None:
            raise inkex.AbortExtension('Could not find the running Inkscape.')
        spawn_detached(helper, os.getpid(), inkscape_pid, app_id_tag(inkscape_pid),
                       self.document_path() or '')


if __name__ == '__main__':
    RestartInkscape().run()
