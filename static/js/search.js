const socket = io();
const logContainer = document.getElementById('logContainer');
const progressCard = document.getElementById('progressCard');
const progressBar = document.getElementById('searchProgress');
const progressText = document.getElementById('progressText');

// Function to stop the current search
function stopSearch() {
    console.log("Stopping search...");
    fetch('/api/stop_search', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        console.log('Stop search response:', data);
        if (data.status === 'success') {
            logContainer.innerHTML += '<p class="log-entry text-danger">Recherche arrêtée par l\'utilisateur</p>';
            logContainer.scrollTop = logContainer.scrollHeight;
        } else {
            logContainer.innerHTML += `<p class="log-entry text-danger">Erreur lors de l'arrêt: ${data.message}</p>`;
            logContainer.scrollTop = logContainer.scrollHeight;
        }
    })
    .catch(error => {
        console.error('Error stopping search:', error);
        logContainer.innerHTML += `<p class="log-entry text-danger">Erreur lors de l'arrêt: ${error}</p>`;
        logContainer.scrollTop = logContainer.scrollHeight;
    });
}

socket.on('log_message', function (data) {
    const logEntry = document.createElement('p');
    logEntry.className = 'log-entry';
    logEntry.textContent = data.message;
    logContainer.appendChild(logEntry);
    logContainer.scrollTop = logContainer.scrollHeight;
});

socket.on('total_articles', function (data) {
    progressCard.style.display = 'block';
    progressBar.style.width = '0%';
    progressBar.textContent = '0%';
    progressText.textContent = `Processing articles: 0 / ${data.total}`;
});

socket.on('results_count', function (data) {
    $('#resultsCountCard').show();
    $('#resultsCountText').text(`Found ${data.total} total results, processing up to ${data.max_articles}`);
});

socket.on('progress', function (data) {
    progressCard.style.display = 'block';
    progressBar.style.width = `${data.value}%`;
    progressBar.textContent = `${data.value}%`;
    progressBar.setAttribute('aria-valuenow', data.value);
    progressText.textContent = `Processing articles: ${data.saved} / ${data.total}`;
});

socket.on('search_complete', function (data) {
    const searchBtn = document.getElementById('searchBtn');
    const stopBtn = document.getElementById('stopBtn');
    searchBtn.disabled = false;
    searchBtn.textContent = 'Search';
    stopBtn.disabled = true;
    progressBar.classList.remove('progress-bar-animated');
});

function updateDateInputs() {
    const searchBy = document.getElementById('search_by').value;
    const yearRangeInputs = document.querySelector('#year_range_inputs');
    const decadeDiv = document.getElementById('decade_selector');

    if (searchBy === 'decade') {
        yearRangeInputs.style.display = 'none';
        decadeDiv.style.display = 'block';
        document.getElementById('start_year').value = '';
        document.getElementById('end_year').value = '';
    } else if (searchBy === 'all_time') {
        yearRangeInputs.style.display = 'none';
        decadeDiv.style.display = 'none';
        document.getElementById('start_year').value = '';
        document.getElementById('end_year').value = '';
        document.getElementById('decade_select').value = '';
    } else {
        yearRangeInputs.style.display = 'block';
        decadeDiv.style.display = 'none';
        document.getElementById('decade_select').value = '';
    }
}

document.getElementById('search_by').addEventListener('change', updateDateInputs);
document.addEventListener('DOMContentLoaded', function () {
    updateDateInputs();
});

document.getElementById('search_by').addEventListener('change', updateDateInputs);
document.addEventListener('DOMContentLoaded', function () {
    updateDateInputs();
});

// Add event listener to the search_by dropdown
document.getElementById('search_by').addEventListener('change', updateDateInputs);

// Initialize the UI when DOM is loaded
document.addEventListener('DOMContentLoaded', function () {
    updateDateInputs();
});

// Update form submission handler to process the appropriate date inputs
document.getElementById('searchForm').addEventListener('submit', function (e) {
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
    const stopBtn = document.getElementById('stopBtn');
    searchBtn.disabled = true;
    stopBtn.disabled = false;
    searchBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Searching...';

    // Create the form data object
    const formData = {
        query: document.getElementById('query').value,
        newspapers: document.getElementById('newspapers').value,
        cantons: document.getElementById('cantons').value,
        correction_method: document.getElementById('correction_method').value,
        search_by: document.getElementById('search_by').value
    };

    // Only add the searches parameter if it's not "all"
    const searches = document.getElementById('searches').value.trim();
    if (searches !== 'all' && searches !== '') {
        formData.searches = searches;
    }

    // Handle date parameters based on search type
    const searchBy = document.getElementById('search_by').value;

    if (searchBy === 'decade') {
        // Use the selected decade
        const selectedDecade = document.getElementById('decade_select').value;
        if (selectedDecade) {
            const [startYear, endYear] = selectedDecade.split('-');
            formData.start_year = startYear;
            formData.end_year = endYear;
        }
    } else {
        // Use the start and end year inputs
        const startYear = document.getElementById('start_year').value.trim();
        const endYear = document.getElementById('end_year').value.trim();

        if (startYear) formData.start_year = startYear;
        if (endYear) formData.end_year = endYear;
    }

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
