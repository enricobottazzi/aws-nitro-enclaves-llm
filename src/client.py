"""
Client to send prompts to the enclave server running the LLM
"""
import json
import socket
import subprocess


def get_cid():
    """
    Determine CID of Current Enclave
    """
    with subprocess.Popen(
        ["/bin/nitro-cli", "describe-enclaves"],
        stdout=subprocess.PIPE
    ) as proc:
        output = json.loads(proc.communicate()[0].decode())
        enclave_cid = output[0]["EnclaveCID"]
        return enclave_cid


def send_prompt(prompt):
    """
    Send a prompt to the enclave server and receive the response
    """
    # Create a vsock socket object
    sock_connect = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)

    # Get CID from command line parameter
    cid = get_cid()

    # The port should match the server running in enclave
    port = 5000

    # Connect to the server
    sock_connect.connect((cid, port))

    # Send prompt to the server running in enclave
    sock_connect.send(str.encode(json.dumps({"prompt": prompt})))

    # receive data from the server
    received_data = sock_connect.recv(4096).decode()

    # parse response
    parsed = json.loads(received_data)

    # pretty print response
    print(json.dumps(parsed, indent=4, sort_keys=True))

    return parsed


def main():
    """
    Main function to send a dummy prompt to the enclave
    """
    prompt = "explain what hello world means"
    print(f"Sending prompt: {prompt}")
    response = send_prompt(prompt)
    print(f'Response: {response}')


if __name__ == '__main__':
    main()
