import socket

class SocketManager:
    def __init__(self, host='localhost', port=8080):
        self.host = host
        self.port = port
        self.server_socket = None
        self.client_socket = None

    def start_server(self):
        """Démarre un serveur socket."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            print(f"Serveur démarré sur {self.host}:{self.port}")
        except Exception as e:
            print(f"Erreur lors du démarrage du serveur : {e}")

    def accept_client(self):
        """Accepte une connexion client."""
        try:
            self.client_socket, addr = self.server_socket.accept()
            print(f"Connexion acceptée de {addr}")
        except Exception as e:
            print(f"Erreur lors de l'acceptation du client : {e}")

    def send_message(self, message):
        """Envoie un message au client."""
        try:
            if self.client_socket:
                self.client_socket.sendall(message.encode('utf-8'))
        except Exception as e:
            print(f"Erreur lors de l'envoi du message : {e}")

    def receive_message(self):
        """Reçoit un message du client."""
        try:
            if self.client_socket:
                return self.client_socket.recv(1024).decode('utf-8')
        except Exception as e:
            print(f"Erreur lors de la réception du message : {e}")
            return None

    def close_connection(self):
        """Ferme les connexions."""
        try:
            if self.client_socket:
                self.client_socket.close()
            if self.server_socket:
                self.server_socket.close()
            print("Connexions fermées.")
        except Exception as e:
            print(f"Erreur lors de la fermeture des connexions : {e}")