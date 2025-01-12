import argparse
import socket
import shlex
import subprocess
import sys
import textwrap
import threading

def execute(cmd):
    cmd = cmd.strip()  # sets up execute function, receives a command, runs it and returns output as a string
    if not cmd:
        return
    output = subprocess.check_output(shlex.split(cmd),
                                     stderr=subprocess.STDOUT)  # check_output runs a command on local os, returns the output from the command
    return output.decode()  # return output as a decoded string

if __name__ == "__main__":
    parser = argparse.ArgumentParser(  # creates a command line using the argparse module
        description="BHP Net Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""Example:     
            netcat.py -t 192.168.1.108 -p 5555 -l -c #command shell
            netcat.py -t 192.168.1.108 -p 5555 -l -u=mytest.txt # upload to file
            netcat.py -t 192.168.1.108 -p 5555 -l -e\"cat /etc/passwd\" execute command
            echo "ABC" | ./netcat.py -t 192.168.1.108 -p 5555 #connect to server
            """))  # provides example usage when the user invokes help

    parser.add_argument("-c", "--command", action="store_true", help="command shell")  # provides arguments for how the program should behave
    parser.add_argument("-e", "--execute", help="execute specified command")
    parser.add_argument("-l", "--listen", action="store_true", help="listen")
    parser.add_argument("-p", "--port", type=int, default=5555, help="specified port")
    parser.add_argument("-u", "--upload", help="upload file")
    parser.add_argument("-t", "--target", default="0.0.0.0", help="specified target")  # added target argument

    args = parser.parse_args()  # parse the arguments

    if args.listen:
        buffer = ""  # invokes netcat object with empty string
    else:
        buffer = sys.stdin.read()

    nc = NetCat(args, buffer.encode())
    nc.run()

class NetCat:
    def __init__(self, args, buffer=None):  # initiates the netcat object from command line and buffer
        self.args = args
        self.buffer = buffer
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # creates socket object

    def run(self):
        if self.args.listen:
            self.listen()  # if a listener, called listen method
        else:
            self.send()  # otherwise send method

    def send(self):
        self.socket.connect((self.args.target, self.args.port))  # connects to target and port, if we have buffer sends to target
        if self.buffer:
            self.socket.send(self.buffer)

        try:  # sets up a try/catch block so we can manually close the connection
            while True:  # starts a loop so we can receive data from the target
                recv_len = 1
                response = ""
                while recv_len:
                    data = self.socket.recv(4096)
                    recv_len = len(data)
                    response += data.decode()  # accumulate response
                    if recv_len < 4096:
                        break  # if no more data, breaks loop
                if response:
                    print(response)
                    buffer = input("> ")
                    buffer += "\n"
                    self.socket.send(buffer.encode())  # sends interactive input
        except KeyboardInterrupt:
            print("USER TERMINATED")
            self.socket.close()
            sys.exit()  # loop continues until user presses CTRL + C

    def listen(self):
        self.socket.bind((self.args.target, self.args.port))  # listen method binds to target and port
        self.socket.listen(5)
        while True:  # listens in a loop
            client_socket, _ = self.socket.accept()
            client_thread = threading.Thread(  # passing connected socket to the handle method
                target=self.handle, args=(client_socket,)
            )
            client_thread.start()

    def handle(self, client_socket):
        if self.args.execute:   # if command should be executed, passes to execute function and sends output back to socket
            output = execute(self.args.execute)
            client_socket.send(output.encode())
        elif self.args.upload:      # if file uploaded, sets up loop to listen for content and recieve until no more incoming data
            file_buffer = b""
            while True:
                data = client_socket.recv(4096)
                if data:
                    file_buffer += data
                else:
                    break

            with open(self.args.upload, "wb") as f:
                f.write(file_buffer)
            message = f"SAVED FILE {self.args.upload}"
            client_socket.send(message.encode())

        elif self.args.command:     # if a shell is created, sets up a loop, sends a prompt to the sender and waits for command string to come back
            cmd_buffer = b""
            while True:
                try:
                    while "\n" not in cmd_buffer.decode():
                        cmd_buffer += client_socket.recv(64)
                    response = execute(cmd_buffer.decode())
                    if response:
                        client_socket.send(response.encode())
                    cmd_buffer = b""
                except Exception as e:
                    print(f"SERVER KILLED {e}")
                    self.socket.close()
                    sys.exit()
