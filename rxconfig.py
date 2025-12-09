import reflex as rx

config = rx.Config(
    app_name="mvp_bot",
    api_url="http://0.0.0.0:8000",
    deploy_url="http://0.0.0.0:3000",
    backend_port=8000,
    frontend_port=3000,
)
