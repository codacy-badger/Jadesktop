import pathlib
import subprocess
import os
import json
import Jade.Menu
import time
import gi
import dbus
gi.require_version('Wnck', '3.0')
gi.require_version('Notify', '0.7')
from gi.repository import Wnck, Gio, Notify, Gdk
from Jade.Settings import Options
from JAK.Utils import JavaScript, Instance
from JAK.Utils import getScreenGeometry
from JAK.Widgets import Dialog
Notify.init("Jade")


def notify(title, msg):
    Notify.Notification.new(title, msg, "dialog-information").show()


def run(command, shell=False):
    proc = subprocess.Popen(command, shell=shell, stdout=subprocess.PIPE)
    return proc


class Session():
    def __init__(self):
        self.desktop_session = os.environ.get('DESKTOP_SESSION')

    @staticmethod
    def logOut():
        if not Session.get_pkg_manager_state():
            run('loginctl terminate-session $XDG_SESSION_ID', shell=True)
        else:
            notify("Warnning", "Cannot log out, instalation or update in progress.")

    @staticmethod
    def powerOff():
        if not Session.get_pkg_manager_state():
            run(['systemctl', 'poweroff'])
        else:
            notify("Information", "Instalation or update in progress, your session is scheduled to shutdown, locking in 10s Goodbye.")
            time.sleep(10)
            Session.lock()
            while Session.get_pkg_manager_state() == True:
                time.sleep(0.2)
            Session.powerOff()

    @staticmethod
    def reboot():
        if not Session.get_pkg_manager_state():
            run(['systemctl', 'reboot'])
        else:
            notify("Information", "Instalation or update in progress, your session is scheduled to reboot, locking in 10s Goodbye.")
            time.sleep(10)
            Session.lock()
            while Session.get_pkg_manager_state() == True:
                time.sleep(0.2)
            Session.reboot()

    @staticmethod
    def suspend():
        if not Session.get_pkg_manager_state():
            run(['systemctl', 'suspend'])
        else:
            notify("Information", "Instalation or update in progress, your session is scheduled to standby, locking in 10s Goodbye.")
            time.sleep(10)
            Session.lock()
            while Session.get_pkg_manager_state() == True:
                time.sleep(0.2)
            Session.suspend()

    @staticmethod
    def lock():
        run(['light-locker-command', '-l'])

    @staticmethod
    def get_pkg_manager_state():
        return os.path.isfile("/var/lib/pacman/db.lck")

    def get_desktop_session(self):
        return self.desktop_session

    @staticmethod
    def userCSS():
        user_folder = Desktop.getHome()
        path = f"{user_folder}/.config/jade/theme/style.css"
        if os.path.exists(path):
            try:
                with open(path, "r", encoding='utf-8') as file:
                    return file.read()
            except Exception as err:
                print(err)


class Desktop:
    def __init__(self):
        self.minimized_windows = []
        self.next_window_pos = "left"
        self.panel_open = False
        self.branch_lock = {"branch":""}
        self.get_screen().connect("window-opened", self.window_open_cb)
        self.get_screen().connect('window-closed', self.window_closed_cb)
        self.get_screen().connect('active-workspace-changed', self.active_workspace_changed_cb)
        self.get_screen().connect('active-window-changed', self.active_window_changed_cb)
        self.screen = Gdk.Screen.get_default()
        self.screen.connect('size-changed', self._ajust_size_window_cb)
        self.screen.connect('monitors-changed', self._ajust_size_window_cb)

        self.ignore_windows = (
            "Guake!", "plank", "Steam Login", "Manjaro Hello", "Manjaro Linux Installer"
            )


    def _ajust_size_window_cb(self, gdk_screen):
        primary_screen = getScreenGeometry()
        win = Instance.retrieve("win")
        win.resize(primary_screen.width(), primary_screen.height())


    def workspace_exec(self, cmd):
        run(f"""
            if ! pgrep -x '{cmd}' > /dev/null; then
                {cmd}
            fi
            """, shell=True)


    def active_window_changed_cb(self, screen, previously_active_window):
        if previously_active_window is not None:
            if previously_active_window.get_name() == "Guake!":
                self.hide_terminal()


    def active_workspace_changed_cb(self, screen, previously_active_space):
        workspace_name = screen.get_active_workspace().get_name()
        workspaces = ["workspace1", "workspace2", "workspace3", "workspace4"]
        for space in workspaces:
            if workspace_name.lower().replace(" ", "") == space:
                config = Desktop.loadSettings()[space].split(" ")
                for cmd in config:
                    if cmd:
                        self.workspace_exec(cmd)


    def toggle(self):
        # wnck only works on xorg
        if not self.minimized_windows:
            self.minimize_windows()
            win = Instance.retrieve("win")
            win.activateWindow()

        elif self.minimized_windows and not self.panel_open:
            for window in self.minimized_windows:
                if window and window.is_minimized():
                    window.unminimize(int(time.time()))
            self.clearWindows()

    def get_screen(self):
        return Wnck.Screen.get_default()

    def workspace(self):
        self.get_screen().get_active_workspace()

    def hide_terminal(self):
        bus = dbus.SessionBus()
        service = bus.get_object('org.guake3.RemoteControl', '/org/guake3/RemoteControl')
        interface = dbus.Interface(service, dbus_interface='org.guake3.RemoteControl')
        interface.hide()

    def minimize_windows(self):
        self.hide_terminal()
        monitor = getScreenGeometry()
        windows = self.get_screen().get_windows()
        for window in windows:
            w_name = window.get_name()
            if not w_name.startswith(self.ignore_windows):
                window_position = window.get_geometry()
                if not window.is_minimized():
                    _type = window.get_window_type()
                    if _type != Wnck.WindowType.DESKTOP and monitor.width() > window_position[0]:
                        self.minimized_windows.append(window)
                        window.minimize()

    def autoTile(self):
        settings = Desktop.loadSettings()
        if settings["autoTile"]:
            monitor = getScreenGeometry()
            windows = self.get_screen().get_windows()            
            for window in windows: 
                actions = window.get_actions()  
                if not actions.MAXIMIZE:
                    w_name = window.get_name()
                    
                    if not w_name.startswith(self.ignore_windows):
                        half_screen_size = float(monitor.width() / 2)
                        window_x = float(window.get_geometry()[0])
                        window_width = float(window.get_geometry()[2])
                        print(window_width)
                        _type = window.get_window_type()
                        if not window.is_skip_tasklist() and window_x != half_screen_size or window_x != 0.0 \
                                or window_width != half_screen_size and not window.is_maximized() \
                                and not window.is_minimized() and not window.is_fullscreen() \
                                and _type == Wnck.WindowType.NORMAL:
                            gravity = Wnck.WindowGravity.STATIC
                            dock_size = 48
                            if self.next_window_pos == "left":
                                self.next_window_pos = "right"
                                x = 0

                            elif self.next_window_pos == "right":
                                self.next_window_pos = "left"
                                x = half_screen_size

                            geometry_mask = Wnck.WindowMoveResizeMask.X | Wnck.WindowMoveResizeMask.Y | \
                                            Wnck.WindowMoveResizeMask.WIDTH | Wnck.WindowMoveResizeMask.HEIGHT

                            window.set_geometry(gravity, geometry_mask, x, 0, half_screen_size, monitor.height()
                                                - dock_size)

                    elif w_name == "Manjaro Linux Installer":
                        window.make_above()
                        window.set_fullscreen(True)
                        window.set_window_type(Wnck.WindowType.SPLASHSCREEN)


    def setPanelVisible(self, value):
        self.panel_open = value

    def window_open_cb(self, screen, window):
        if window.get_name() != "Guake!":
            self.hide_terminal()
        if Desktop.loadSettings()["tourDone"]:
            _type = window.get_window_type()
            if _type == Wnck.WindowType.DESKTOP:
                pass
            elif _type == Wnck.WindowType.NORMAL:
                self.clearWindows()
                self.autoTile()
        else:
            self.autoTile()
            time.sleep(0.50)
            self.minimize_windows()

    def window_closed_cb(self, screen, closed_window):
        for w in self.minimized_windows:
            if w is closed_window:
                self.minimized_windows.remove(closed_window)

    def clearWindows(self):
        self.minimized_windows.clear()

    @staticmethod
    def getPath():
        return str(pathlib.Path(__file__).parent.parent.absolute())

    @staticmethod
    def getHome():
        return str(pathlib.Path.home())

    @staticmethod
    def toggleSearch():
        JavaScript.send("desktop.toggleSearch();")

    @staticmethod
    def about():
        items = json.dumps({
            "author": "Vitor Lopes",
            "title": "Just Another Desktop Enviroment",
            "url": "https://github.com/codesardine/Jadesktop/",
            "license": "GPL"
        })
        return items

    @staticmethod
    def screenToggle():
        desktop = Instance.retrieve("desktop")
        desktop.setPanelVisible(False)
        desktop.toggle()

    @staticmethod
    def setBackground():
        from JAK.Widgets import FileChooserDialog
        window = Instance.retrieve("win")
        image = FileChooserDialog(
            parent=window, file_type="*.jpeg, *.jpg", title="Chose a image").choose_file()
        if image and os.path.isfile(image):
            window = Instance.retrieve("win")
            window.setBackgroundImage(image)
            Desktop.saveSettings("background", image)

    @staticmethod
    def getBackground():
        try:
            background = Desktop.loadSettings()["background"]
        except Exception:
            background = f"{Desktop.getPath()}/themes/default/backgrounds/background.jpg"
        return background

    @staticmethod
    def getJS():
        menu = Jade.Menu.Get().items()
        settings = Desktop.loadSettings()
        return f"const Jade = {{}};Jade.menu = {json.dumps(menu)};Jade.settings = {json.dumps(settings)}"

    @staticmethod
    def updateMenu():
        menu = Jade.Menu.Get().items()
        JavaScript.send(f"Jade.menu = {json.dumps(menu)}")

    @staticmethod
    def toggleSettings():
        JavaScript.send("desktop.toggleSettings();")

    @staticmethod
    def toggleLauncher():
        JavaScript.send("desktop.toggleLauncher();")

    def setBranch(self, desired_branch):
        current_branch = Desktop.getBranch()
        if current_branch != desired_branch:
            if self.branch_lock["branch"] == "":
                self.branch_lock["branch"] = desired_branch.upper()
                notify(f"Setting branch to {desired_branch.upper()} and synchronising mirrors.", "Might take a while.")
               
                def update():
                    run(["pamac-manager", "--updates"])

                def package_sync_callback(*args):
                    print(args)
                    window = Instance.retrieve("win")
                    msg = f"Would you like to update your software and operating system from {self.branch_lock['branch']} branch now?"
                    Dialog.question(window, " ", msg, update)  
                    self.branch_lock["branch"] = "" 
                    JavaScript.send(f"""
                    desktop.elem(`#{self.branch_lock["branch"]}-btn`).checked = true
                    """)

                def branch_sync_callback(sucprocess: Gio.Subprocess, result: Gio.AsyncResult, data):
                    proc1.communicate_utf8_finish(result) 
                    notify("Mirrors done, Synchronising packages", "") 
                    proc2 = Gio.Subprocess.new([
                        'pkexec', 'pacman', '-Sy'
                        ], Gio.SubprocessFlags.STDIN_PIPE | Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
                    proc2.communicate_utf8_async('package sync', None, package_sync_callback, None)                                  
                
                cmd = ['pkexec', 'pacman-mirrors', '--fasttrack', '--api', '--set-branch', f'{desired_branch}']
                proc1 = Gio.Subprocess.new(cmd, Gio.SubprocessFlags.STDIN_PIPE | Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
                proc1.communicate_utf8_async('mirrors sync', None, branch_sync_callback, None) 

            else:
                notify(f"Hold on, still changing to {self.branch_lock['branch']}.", "") 
                JavaScript.send(f"""
                    desktop.elem(`#{current_branch}-btn`).checked = true
                    """)

    @staticmethod
    def getBranch():
        p = run('cat /etc/pacman-mirrors.conf | grep "Branch ="', shell=True)
        output = p.stdout.readline().decode(
            "utf-8").replace("Branch = ", "").replace("#", "").strip()
        return output

    @staticmethod
    def restoreDefaultsDialog():
        window = Instance.retrieve("win")
        msg = "Some of your manual configuration under your HOME folder will be lost, Would you like to proceed?"
        Dialog.question(window, " ",
                             msg, Desktop.restoreDefaults)

    @staticmethod
    def restoreDefaults():
        home = os.path.expanduser("~")
        # TODO backup old files
        run(f"cp -r /etc/skel {home}/", shell=True)
        from JAK.Widgets import Dialog
        window = Instance.retrieve("win")
        msg = "Profile defaults have been set on your home directory."
        Dialog.information(window, "Set Defaults", msg)

    @staticmethod
    def saveSettings(key, value):
        options = Options()
        options.save(key, value)

    @staticmethod
    def loadSettings():
        options = Options()
        return options.load()

