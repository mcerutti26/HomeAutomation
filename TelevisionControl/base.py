from roku import Roku
from adb_shell.auth.sign_pythonrsa import PythonRSASigner
from androidtv import AndroidTVSync
from adb_shell.auth.keygen import keygen
import os
import subprocess
import PySimpleGUI as sg


# Television class to connect to the TV and send basic remote commands
class Television:
    def __init__(self, name, operating_system: str, ip_address=None):
        # Name the TV, record the operating system, and initialize mute status and OS variables
        self.name = name
        # The only OSs supported are roku and android
        if operating_system.lower() not in ['roku', 'android']:
            raise ValueError(
                "Operating system must be Roku or Android. No other operating systems are currently supported.")
        else:
            self.operating_system = operating_system
        # the roku and android attributes will become Roku or AndroidTVSync instances after a successful connection
        # one of attributes will be used as the controller to send commands through
        self.roku = None
        self.android = None
        self._muted = None
        # If an ip address is passed during initialization, the Television instance will autoconnect
        if ip_address:
            self.connect(ip_address)

    # connect() needs to be run successfully prior to any other commands
    # you will need the ip address of your television to proceed
    def connect(self, ip_address):
        if self.operating_system.lower() == 'roku':
            # the roku OS is much friendlier to python with the Roku package
            self.roku = Roku(ip_address)
        elif self.operating_system.lower() == 'android':
            # format command text to be run as a subprocess command
            command = ("adb connect " + ip_address + ":5555")
            # send command
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            out, err = process.communicate()
            # generate the key pair and save the private key
            private_key_path = os.path.expanduser('~/.android/adbkey')
            keygen(private_key_path)
            with open(private_key_path, 'rb') as f:
                priv = f.read()
            with open(os.path.expanduser('~/.android/adbkey.pub'), 'r') as f:
                pub = f.read()
            # instantiate the PythonRSASigner with the generated keys
            signer = PythonRSASigner(pub, priv)
            params = {'adb_server_ip': os.getenv('adb_server_ip')}
            # connect to the android tv
            self.android = AndroidTVSync(ip_address, signer=signer, **params)
            self.android.adb_connect()
        # Assuming connection is during boot up, the TV will not be muted
        self.muted(False)

    @property
    def muted(self):
        # if this is the first check of the muted attribute, get (android) or set (roku) the mute status on the TV
        # and record it
        if self._muted is None:
            if self.roku:
                # I am unable to check if the roku tv is muted so I am forced to turn on the sound via dialing the
                # volume up and back down
                self.roku.volume_up()
                self.roku.volume_down()
                self._muted = False
            elif self.android:
                self._muted = self.android.get_properties_dict().get('is_volume_muted')
        return self._muted

    @muted.setter
    def muted(self, value: bool):
        self._muted = value

    def toggle_mute(self):
        # both roku and android allow you to perform toggle mute the same as a TV remote mute button
        if self.roku:
            self.roku.volume_mute()
        elif self.android:
            self.android.mute_volume()
        if self.muted:
            self.muted = False
        else:
            self.muted = True

    def mute(self):
        if not self.muted:
            self.toggle_mute()
        self.muted = True

    def unmute(self):
        if self.muted:
            self.toggle_mute()
        self.muted = False

    def right(self):
        if self.roku:
            self.roku.right()
        elif self.android:
            self.android.right()

    def left(self):
        if self.roku:
            self.roku.left()
        elif self.android:
            self.android.left()

    def down(self):
        if self.roku:
            self.roku.down()
        elif self.android:
            self.android.down()

    def up(self):
        if self.roku:
            self.roku.up()
        elif self.android:
            self.android.up()

    def select(self):
        # select is the equivalent of clicking the center button on a remote dpad, aka select or enter
        if self.roku:
            self.roku.select()
        elif self.android:
            self.android.enter()

    def back(self):
        if self.roku:
            self.roku.back()
        elif self.android:
            self.android.back()


# PySimpleGUI to create a virtual remote control where you can flip between which tv to control
# This GUI is specific my game room with 3 TVs, 1 Roku on top of 2 Androids
# Why 3 TVs? Sports
class TelevisionGUI:
    def __init__(self):
        # As described above, the tv layout and assignment is specific to my room
        self.tvs = {
            'TopTV': Television('TopTV', 'roku'),
            'RightTV': Television('RightTV', 'android'),
            'LeftTV': Television('LeftTV', 'android')
        }
        self.tvs['TopTV'].connect(os.getenv('TopTVIP'))
        self.tvs['RightTV'].connect(os.getenv('RightTVIP'))
        self.tvs['LeftTV'].connect(os.getenv('LeftTVIP'))
        # layout the GUI as a tv controller with a drop down menu for which tv to control
        layout = [
            [sg.Text('Select TV:', font='Any 30'),
             sg.Combo(['TopTV', 'RightTV', 'LeftTV'], key='tv_select', font='Any 30')],
            [sg.Button('Mute', font='Any 30', auto_size_button=True),
             sg.Button('Unmute', font='Any 30', auto_size_button=True)],
            [sg.Column([[sg.Button('↑', font='Any 30', auto_size_button=True)]], justification='center')],
            [sg.Column([[sg.Button('←', font='Any 30', auto_size_button=True),
                         sg.Button('Select', font='Any 30', auto_size_button=True),
                         sg.Button('→', font='Any 30', auto_size_button=True)]], justification='center')],
            [sg.Column([[sg.Button('↓', font='Any 30', auto_size_button=True)]], justification='center')],
            [sg.Button('Back', font='Any 30', auto_size_button=True)]
        ]

        self.window = sg.Window('TV Control', layout, finalize=True, size=(400, 400), auto_size_buttons=True,
                                auto_size_text=True)
        # Leave the GUI open until window closed
        while True:
            event, values = self.window.read()
            if event == sg.WIN_CLOSED:
                break
            elif event == 'Connect':
                self.connect(values['tv_ip'], values['tv_select'])
            elif event == 'Mute':
                self.mute(values['tv_select'])
            elif event == 'Unmute':
                self.unmute(values['tv_select'])
            elif event == '↑':
                self.up(values['tv_select'])
            elif event == '↓':
                self.down(values['tv_select'])
            elif event == '←':
                self.left(values['tv_select'])
            elif event == '→':
                self.right(values['tv_select'])
            elif event == 'Select':
                self.select(values['tv_select'])
            elif event == 'Back':
                self.back(values['tv_select'])

    # Forward on the GUI command to the specific instance of a Television variable
    def connect(self, ip, tv_name):
        try:
            self.tvs[tv_name].connect(ip)
            sg.popup(f"{tv_name} connected successfully!")
        except Exception as e:
            sg.popup_error(str(e))

    def mute(self, tv_name):
        if self.tvs[tv_name]:
            self.tvs[tv_name].mute()

    def unmute(self, tv_name):
        if self.tvs[tv_name]:
            self.tvs[tv_name].unmute()

    def up(self, tv_name):
        if self.tvs[tv_name]:
            self.tvs[tv_name].up()

    def down(self, tv_name):
        if self.tvs[tv_name]:
            self.tvs[tv_name].down()

    def left(self, tv_name):
        if self.tvs[tv_name]:
            self.tvs[tv_name].left()

    def right(self, tv_name):
        if self.tvs[tv_name]:
            self.tvs[tv_name].right()

    def back(self, tv_name):
        if self.tvs[tv_name]:
            self.tvs[tv_name].back()

    def select(self, tv_name):
        if self.tvs[tv_name]:
            self.tvs[tv_name].select()


# Test
if __name__ == "__main__":
    TelevisionGUI()
