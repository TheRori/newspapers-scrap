const socket = io();
const logContainer = document.getElementById('logContainer');
const progressCard = document.getElementById('progressCard');
const progressBar = document.getElementById('searchProgress');
const progressText = document.getElementById('progressText');

socket.on('log_message', function(data) {
    const logEntry = document.createElement('p');
    logEntry.className = 'log-entry';
    logEntry.textContent = data.message;
    logContainer.appendChild(logEntry);
    logContainer.scrollTop = logContainer.scrollHeight;
});

socket.on('total_articles', function(data) {
    progressCard.style.display = 'block';
    progressBar.style.width = '0%';
    progressBar.textContent = '0%';
    progressText.textContent = `Processing articles: 0 / ${data.total}`;
});

socket.on('progress', function(data) {
    progressCard.style.display = 'block';
    progressBar.style.width = `${data.value}%`;
    progressBar.textContent = `${data.value}%`;
    progressBar.setAttribute('aria-valuenow', data.value);
    progressText.textContent = `Processing articles: ${data.saved} / ${data.total}`;
});

socket.on('search_complete', function(data) {
    const searchBtn = document.getElementById('searchBtn');
    searchBtn.disabled = false;
    searchBtn.textContent = 'Search';
    progressBar.classList.remove('progress-bar-animated');
});

document.getElementById('searchForm').addEventListener('submit', function(e) {
    e.preventDefault();
    console.log("Search form submitted");
    logContainer.innerHTML = '';
    progressCard.style.display = 'block';
    progressBar.style.width = '0%';
    progressBar.textContent = '0%';
    progressBar.setAttribute('aria-valuenow', 0);
    progressBar.classList.add('progress-bar-animated');
    progressText.textContent = 'Processing articles: 0 / 0';

    const searchBtn = document.getElementById('searchBtn');
    searchBtn.disabled = true;
    searchBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Searching...';

    const formData = {
        query: document.getElementById('query').value,
        newspapers: document.getElementById('newspapers').value,
        cantons: document.getElementById('cantons').value,
        pages: document.getElementById('pages').value,
        deq: document.getElementById('deq').value,
        yeq: document.getElementById('yeq').value
    };

    fetch('/api/search', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
    })
    .catch(error => {
        console.error('Error:', error);
        logContainer.innerHTML += '<p class="log-entry text-danger">Error: ' + error + '</p>';
        searchBtn.disabled = false;
        searchBtn.textContent = 'Search';
        progressCard.style.display = 'none';
    });
});