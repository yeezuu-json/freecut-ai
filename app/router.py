from PySide6.QtWidgets import QStackedWidget, QWidget


class Router:
    def __init__(self):
        self.stack = QStackedWidget()
        self.routes: dict[str, QWidget] = {}

    def add_route(self, name: str, page: QWidget):
        self.routes[name] = page
        self.stack.addWidget(page)

    def go_to(self, name: str):
        page = self.routes.get(name)

        if page is None:
            raise ValueError(f"Route '{name}' does not exist.")

        self.stack.setCurrentWidget(page)

    def current_route(self) -> str | None:
        current_widget = self.stack.currentWidget()

        for name, page in self.routes.items():
            if page == current_widget:
                return name

        return None