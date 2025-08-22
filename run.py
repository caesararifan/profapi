# /my-api-project/run.py

from app import create_app

app = create_app()

if __name__ == '__main__':
    # Server hanya akan berjalan di localhost (127.0.0.1)
    app.run(debug=True, port=5000)