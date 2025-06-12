
---

## MongoDB Integration

This application supports storing processed articles in a MongoDB Atlas database for scalable storage and querying.

### MongoDB Setup
1. Create a MongoDB Atlas cluster (or use your own MongoDB server).
2. Obtain your MongoDB connection URI.
3. Configure your credentials in `newspapers_scrap/config/secrets.yaml`:

```yaml
mongodb:
  uri: "<your-mongodb-uri>"
  database: "articles"
  collection: "press_processed"
```

- `uri`: Your MongoDB connection string (keep this secret!)
- `database`: The database name (default: `articles`)
- `collection`: The collection name (default: `press_processed`)

## Real-Time Progress & Web Interface

The app features a Flask web interface with real-time progress updates via Socket.IO. This allows you to:
- Push articles to MongoDB
- Track progress with a live progress bar and status messages
- See which articles are new or already present

### Running the Web App

```bash
python -m flask --app app run
```

Or use your preferred method to start the Flask server. By default, the app runs on [http://127.0.0.1:5000](http://127.0.0.1:5000).

### Using the Web Interface
1. Open the web app in your browser.
2. Navigate to the article management section.
3. Use the UI to push articles to MongoDB:
    - Choose to push all or only new articles
    - Watch real-time progress and status updates

## Usage: Pushing Articles to MongoDB

- The push feature is available via the web UI under the article blueprint.
- Progress is tracked and displayed in real time.
- Only new articles are pushed if you select the 'push only new' option (optimized by pre-fetching existing IDs).

## Troubleshooting

## Dependency Management

This project uses [`pip-tools`](https://github.com/jazzband/pip-tools) for dependency management.

- **Add new dependencies** to `requirements.in` (not `requirements.txt`).
- Run `pip-compile requirements.in` to regenerate `requirements.txt` with pinned versions.
- Install dependencies with:
  ```bash
  pip install -r requirements.txt
  ```

To install pip-tools:
```bash
pip install pip-tools
```


- **MongoDB connection errors**: Check your `secrets.yaml` for typos and ensure your IP is whitelisted in MongoDB Atlas.
- **Socket.IO issues**: Ensure Flask-SocketIO is installed and not blocked by firewalls.
- **Web UI not updating**: Refresh the page or check the browser console for errors.
- **Dependencies**: Install all dependencies with `pip install -r requirements.txt`.
- **Python version**: Use Python 3.7 or newer.

## Support
For questions or issues, please open an issue or contact the maintainer.
