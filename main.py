import sys

from PyQt6.QtWidgets import QApplication

from services.api_client import ApiClient
from views.login_view import LoginView


def main() -> None:
    app = QApplication(sys.argv)
    api_client = ApiClient()
    window = LoginView(api_client)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
