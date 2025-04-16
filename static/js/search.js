// Global variables to track multi-task progress
let currentTaskIndex = 0;
let totalTasks = 1;
let completedTasks = 0;
let searchPeriods = [];

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

let totalYears = 1;
let currentYear = 0;


socket.on('overall_progress', function (data) {
    // Update the overall progress bar
    const overallProgressBar = document.getElementById('overallProgress');
    overallProgressBar.style.width = `${data.value}%`;
    overallProgressBar.textContent = `${data.value}%`;
    overallProgressBar.setAttribute('aria-valuenow', data.value);

    // Update the overall progress text
    document.getElementById('overallProgressText').textContent =
        `Task ${data.current_task} of ${data.total_tasks} (${data.value}% overall)`;
});

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
    let countText = `Found ${data.total} total results`;
    if (data.max_articles && data.max_articles < data.total) {
        countText += `, processing up to ${data.max_articles}`;
    }
    if (data.period) {
        countText += ` for period ${data.period}`;
    }
    $('#resultsCountText').text(countText);
});

socket.on('year_progress', function (data) {
    currentYear = data.current_year;
    totalYears = data.total_years;

    // Display which year we're on
    document.getElementById('overallProgressText').textContent =
        `Processing year ${currentYear} of ${totalYears}`;
});

socket.on('progress', function (data) {
    // Update the per-year progress bar
    progressBar.style.width = `${data.value}%`;
    progressBar.textContent = `${data.value}%`;
    progressBar.setAttribute('aria-valuenow', data.value);
    progressText.textContent = `Processing articles: ${data.saved} / ${data.total}`;
});

socket.on('period_update', function (data) {
    document.getElementById('currentPeriodText').textContent = data.period || '-';
});

// Listen for search_started event to initialize task tracking
socket.on('search_started', function (data) {
    console.log('Search started:', data);

    // Initialize task tracking with the total number of tasks
    totalTasks = data.total_tasks || 1;
    currentTaskIndex = 0;
    completedTasks = 0;
    searchPeriods = data.periods || [];

    // Update the current task text
    document.getElementById('currentTaskText').textContent = `(Task 1/${totalTasks})`;

    // If we have periods, update the current period text
    if (searchPeriods.length > 0) {
        document.getElementById('currentPeriodText').textContent = searchPeriods[0] || '-';
    }

    // Update the overall progress text
    document.getElementById('overallProgressText').textContent =
        `Task 1 of ${totalTasks} (0% complete)`;
});

socket.on('task_change', function (data) {
    console.log('Task change:', data);

    // Mark the previous task as completed
    if (currentTaskIndex >= 0) {
        completedTasks++;
    }

    // Update task tracking
    currentTaskIndex = data.current_task - 1;

    // Don't override the total tasks if we already know it
    if (data.total_tasks && (!totalTasks || totalTasks < data.total_tasks)) {
        totalTasks = data.total_tasks;
    }

    // Update the current period text
    document.getElementById('currentPeriodText').textContent = data.period || '-';

    // Update the current task text
    document.getElementById('currentTaskText').textContent = `(Task ${data.current_task}/${totalTasks})`;

    // Reset the current task progress bar
    progressBar.style.width = '0%';
    progressBar.textContent = '0%';
    progressBar.setAttribute('aria-valuenow', 0);

    // Update the progress text
    progressText.textContent = 'Starting new period...';

    // Note: We don't update overall progress here anymore,
    // as it will be handled by the overall_progress event
});

socket.on('search_complete', function (data) {
    const searchBtn = document.getElementById('searchBtn');
    const stopBtn = document.getElementById('stopBtn');
    searchBtn.disabled = false;
    searchBtn.textContent = 'Search';
    stopBtn.disabled = true;
    progressBar.classList.remove('progress-bar-animated');

    // Mark all tasks as completed
    completedTasks = totalTasks;

    // Update the overall progress to 100%
    const overallProgressBar = document.getElementById('overallProgress');
    overallProgressBar.style.width = '100%';
    overallProgressBar.textContent = '100%';
    overallProgressBar.setAttribute('aria-valuenow', 100);

    document.getElementById('overallProgressText').textContent =
        `All ${totalTasks} tasks completed (100%)`;
});

// Add event listeners for our new messages
socket.on('search_scope', function (data) {
    totalYears = data.total_years;
    // Reset the overall progress bar
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

    // Reset progress bars
    progressBar.style.width = '0%';
    progressBar.textContent = '0%';
    progressBar.setAttribute('aria-valuenow', 0);
    progressBar.classList.add('progress-bar-animated');
    progressText.textContent = 'Processing articles: 0 / 0';

    const overallProgressBar = document.getElementById('overallProgress');
    overallProgressBar.style.width = '0%';
    overallProgressBar.textContent = '0%';
    overallProgressBar.setAttribute('aria-valuenow', 0);
    document.getElementById('overallProgressText').textContent = 'Starting search...';

    // Reset period text
    document.getElementById('currentPeriodText').textContent = '-';
    document.getElementById('currentTaskText').textContent = '';

    // Reset task tracking
    currentTaskIndex = 0;
    completedTasks = 0;
    totalTasks = 1;

    const searchBtn = document.getElementById('searchBtn');
    const stopBtn = document.getElementById('stopBtn');
    searchBtn.disabled = true;
    stopBtn.disabled = false;
    searchBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Searching...';
    const startFrom = document.getElementById('start_from').value.trim();

    // Create the form data object
    const formData = {
        query: document.getElementById('query').value,
        cantons: document.getElementById('cantons').value, // This will now get the selected canton code
        correction_method: document.getElementById('correction_method').value,
        search_by: document.getElementById('search_by').value,
        laq: 'fr',
        start_from: parseInt(startFrom)
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
        .then(response => response.json())
        .then(data => {
            console.log('Search API response:', data);

            // The task tracking information will now be handled by the search_started event
        })
        .catch(error => {
            console.error('Error:', error);
            logContainer.innerHTML += '<p class="log-entry text-danger">Error: ' + error + '</p>';
            searchBtn.disabled = false;
            searchBtn.textContent = 'Search';
            progressCard.style.display = 'none';
        });
});
