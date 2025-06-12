
---

# Newspaper Article Extraction & Management App

This application is designed to extract, process, and manage articles from newspaper sources. It provides a robust workflow for scraping articles, cleaning and structuring their content, and managing the resulting dataset through a user-friendly web interface. Optionally, the app supports scalable storage and querying of processed articles via MongoDB Atlas.

## Features
- **Article Extraction:** Scrape articles from supported newspaper sources (local files, online archives, etc.).
- **Content Processing:** Clean, structure, and enrich extracted articles for downstream use.
- **Web Interface:** Manage extraction, monitor progress, and review articles in real time.
- **MongoDB Integration (Optional):** Store processed articles in MongoDB for scalable querying and analytics.
- **Real-Time Progress:** Live progress bar and status updates via Socket.IO during extraction and database operations.

## Article Extraction Workflow

1. **Configure Sources:** Set up your list of newspaper sources (URLs, file paths, etc.) in the configuration files or via the web interface.
2. **Run Extraction:** Use the web interface or command-line tools to start the extraction process. The app will:
    - Fetch articles from configured sources
    - Parse and clean article content
    - Structure metadata (title, date, author, etc.)
3. **Review Results:** Extracted articles are available for review and further processing in the web interface.
4. **(Optional) Push to MongoDB:** Store your processed articles in a MongoDB Atlas database for persistent storage and advanced querying.

## Running the Web App

```bash
python -m flask --app app run
```

By default, the app runs on [http://127.0.0.1:5000](http://127.0.0.1:5000).

### Using the Web Interface
1. Open the web app in your browser.
2. Navigate to the article management section.
3. Start extraction jobs, monitor progress, and review extracted articles.
4. Use the UI to push articles to MongoDB if desired:
    - Choose to push all or only new articles
    - Watch real-time progress and status updates

## MongoDB Integration (Optional)

If you want to store processed articles in MongoDB Atlas:

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

The push feature is available via the web UI under the article blueprint. Progress is tracked and displayed in real time. Only new articles are pushed if you select the 'push only new' option (optimized by pre-fetching existing IDs).

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
