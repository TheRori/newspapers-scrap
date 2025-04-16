// Global variables to track multi-task progress
let currentTaskIndex = 0;
let totalTasks = 1;
let completedTasks = 0;
let searchPeriods = [];

console.log("Connecting to Socket.IO server...");
// Create a Socket.IO connection with explicit URL and options
const socket = io(window.location.protocol + '//' + window.location.host, {
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000,
    timeout: 20000,
    transports: ['websocket', 'polling']
});
const logContainer = document.getElementById('logContainer');
const progressCard = document.getElementById('progressCard');
const progressBar = document.getElementById('searchProgress');
const progressText = document.getElementById('progressText');

// Debug function to log DOM elements
function debugElements() {
    console.log("Debug DOM elements:");
    console.log("logContainer:", logContainer);
    console.log("progressCard:", progressCard);
    console.log("progressBar:", progressBar);
    console.log("progressText:", progressText);
    console.log("searchBtn:", document.getElementById('searchBtn'));
    console.log("stopBtn:", document.getElementById('stopBtn'));
    console.log("overallProgress:", document.getElementById('overallProgress'));
    console.log("currentPeriodText:", document.getElementById('currentPeriodText'));
    console.log("resultsCountText:", document.getElementById('resultsCountText'));
}

// Call debug function on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM fully loaded");
    debugElements();
});

// Add a catch-all event listener to log all events
socket.onAny((event, ...args) => {
    console.log(`DEBUG - Socket.IO event received: ${event}`, args);
});

// Handle Socket.IO connection events
socket.on('connect', function() {
    console.log("Socket.IO connection established successfully!");
    console.log("Socket ID:", socket.id);
    console.log("Socket connected:", socket.connected);
    debugElements();
    
    // Add a log entry to show connection status
    if (logContainer) {
        logContainer.innerHTML += '<p class="log-entry text-success">WebSocket connected</p>';
        logContainer.scrollTop = logContainer.scrollHeight;
    }
});

socket.on('disconnect', function(reason) {
    console.log("Socket.IO connection closed. Reason:", reason);
    
    // Add a log entry to show disconnection
    if (logContainer) {
        logContainer.innerHTML += `<p class="log-entry text-danger">WebSocket disconnected: ${reason}</p>`;
        logContainer.scrollTop = logContainer.scrollHeight;
    }
});

socket.on('connect_error', function(error) {
    console.error("Socket.IO connection error:", error);
    
    // Add a log entry to show connection error
    if (logContainer) {
        logContainer.innerHTML += `<p class="log-entry text-danger">WebSocket connection error: ${error}</p>`;
        logContainer.scrollTop = logContainer.scrollHeight;
    }
});

socket.on('reconnect_attempt', function(attemptNumber) {
    console.log("Socket.IO reconnection attempt:", attemptNumber);
});

socket.on('reconnect', function(attemptNumber) {
    console.log("Socket.IO reconnected after", attemptNumber, "attempts");
    
    // Add a log entry to show reconnection
    if (logContainer) {
        logContainer.innerHTML += `<p class="log-entry text-success">WebSocket reconnected after ${attemptNumber} attempts</p>`;
        logContainer.scrollTop = logContainer.scrollHeight;
    }
});

socket.on('reconnect_error', function(error) {
    console.error("Socket.IO reconnection error:", error);
});

socket.on('reconnect_failed', function() {
    console.error("Socket.IO failed to reconnect");
    
    // Add a log entry to show reconnection failure
    if (logContainer) {
        logContainer.innerHTML += '<p class="log-entry text-danger">WebSocket failed to reconnect</p>';
        logContainer.scrollTop = logContainer.scrollHeight;
    }
});

// Handle Socket.IO events
socket.on('log_message', function(data) {
    console.log("Received log_message event:", data);
    handleLogMessage(data);
});

socket.on('progress', function(data) {
    console.log("Received progress event:", data);
    handleProgress(data);
});

socket.on('overall_progress', function(data) {
    console.log("Received overall_progress event:", data);
    handleOverallProgress(data);
});

socket.on('search_started', function(data) {
    console.log("Received search_started event:", data);
    handleSearchStarted(data);
});

socket.on('search_complete', function(data) {
    console.log("Received search_complete event:", data);
    handleSearchComplete(data);
});

socket.on('search_stopped', function(data) {
    console.log("Received search_stopped event:", data);
    handleSearchStopped(data);
});

socket.on('task_change', function(data) {
    console.log("Received task_change event:", data);
    handleTaskChange(data);
});

socket.on('results_count', function(data) {
    console.log("Received results_count event:", data);
    handleResultsCount(data);
});

socket.on('year_progress', function(data) {
    console.log("Received year_progress event:", data);
    handleYearProgress(data);
});

socket.on('article_saved', function(data) {
    console.log("Received article_saved event:", data);
    handleArticleSaved(data);
});

// Event handler functions
function handleLogMessage(data) {
    console.log("Handling log message:", data);
    if (!logContainer) {
        console.error("logContainer is null or undefined");
        debugElements();
        return;
    }
    logContainer.innerHTML += `<p class="log-entry">${data.message}</p>`;
    logContainer.scrollTop = logContainer.scrollHeight;
}

function handleProgress(data) {
    console.log("Handling progress:", data);
    const progressBar = document.getElementById('searchProgress');
    const progressText = document.getElementById('progressText');
    
    if (!progressBar) {
        console.error("progressBar is null or undefined");
        debugElements();
        return;
    }
    
    // Update the progress bar
    progressBar.style.width = `${data.value}%`;
    progressBar.textContent = `${data.value}%`;
    progressBar.setAttribute('aria-valuenow', data.value);
    
    // Update the progress text if it exists
    if (progressText) {
        progressText.textContent = `Processing articles: ${data.saved}/${data.total} (${data.period})`;
    }
    
    // Also update the current period text
    const currentPeriodText = document.getElementById('currentPeriodText');
    if (currentPeriodText) {
        currentPeriodText.textContent = data.period || '-';
    }
}

function handleOverallProgress(data) {
    console.log("Handling overall progress:", data);
    const overallProgressBar = document.getElementById('overallProgress');
    const overallProgressText = document.getElementById('overallProgressText');
    
    if (!overallProgressBar) {
        console.error("overallProgressBar is null or undefined");
        debugElements();
        return;
    }
    
    // Update the overall progress bar
    overallProgressBar.style.width = `${data.value}%`;
    overallProgressBar.textContent = `${data.value}%`;
    overallProgressBar.setAttribute('aria-valuenow', data.value);
    
    // Update the task text if overallProgressText exists
    if (overallProgressText) {
        overallProgressText.textContent = `Task ${data.current_task}/${data.total_tasks}`;
    }
    
    // Also update the currentTaskText element
    const currentTaskText = document.getElementById('currentTaskText');
    if (currentTaskText) {
        currentTaskText.textContent = `(Task ${data.current_task}/${data.total_tasks})`;
    }
}

function handleSearchStarted(data) {
    console.log("Handling search started:", data);
    totalTasks = data.total_tasks;
    searchPeriods = data.periods;
    
    if (!progressCard) {
        console.error("progressCard is null or undefined");
        debugElements();
        return;
    }
    
    progressCard.style.display = 'block';
    
    const searchBtn = document.getElementById('searchBtn');
    const stopBtn = document.getElementById('stopBtn');
    
    if (!searchBtn || !stopBtn) {
        console.error("searchBtn or stopBtn is null or undefined");
        debugElements();
        return;
    }
    
    searchBtn.disabled = true;
    searchBtn.textContent = 'Searching...';
    stopBtn.style.display = 'inline-block';
    stopBtn.disabled = false;
}

function handleSearchComplete(data) {
    console.log("Handling search complete:", data);
    const searchBtn = document.getElementById('searchBtn');
    const stopBtn = document.getElementById('stopBtn');
    
    if (!searchBtn || !stopBtn || !logContainer) {
        console.error("searchBtn, stopBtn, or logContainer is null or undefined");
        debugElements();
        return;
    }
    
    searchBtn.disabled = false;
    searchBtn.textContent = 'Search';
    stopBtn.style.display = 'none';
    logContainer.innerHTML += '<p class="log-entry text-success"><strong>Search completed!</strong></p>';
    logContainer.scrollTop = logContainer.scrollHeight;
}

function handleSearchStopped(data) {
    console.log("Handling search stopped:", data);
    if (!logContainer) {
        console.error("logContainer is null or undefined");
        debugElements();
        return;
    }
    
    logContainer.innerHTML += `<p class="log-entry text-warning">${data.message}</p>`;
    logContainer.scrollTop = logContainer.scrollHeight;
}

function handleTaskChange(data) {
    console.log("Handling task change:", data);
    currentTaskIndex = data.current_task - 1;
    
    const currentPeriodText = document.getElementById('currentPeriodText');
    if (!currentPeriodText) {
        console.error("currentPeriodText is null or undefined");
        debugElements();
        return;
    }
    
    currentPeriodText.textContent = data.period;
}

function handleResultsCount(data) {
    console.log("Handling results count:", data);
    const resultsCountText = document.getElementById('resultsCountText');
    const resultsCountCard = document.getElementById('resultsCountCard');
    
    if (!resultsCountText || !resultsCountCard) {
        console.error("resultsCountText or resultsCountCard is null or undefined");
        debugElements();
        return;
    }
    
    resultsCountCard.style.display = 'block';
    resultsCountText.textContent = `Found ${data.total} results, processing up to ${data.max_articles}`;
}

function handleYearProgress(data) {
    console.log("Handling year progress:", data);
    const yearProgressBar = document.getElementById('yearProgress');
    const yearProgressText = document.getElementById('yearProgressText');
    
    if (!yearProgressBar || !yearProgressText) {
        console.error("yearProgressBar or yearProgressText is null or undefined");
        debugElements();
        return;
    }
    
    yearProgressBar.style.width = `${data.percentage}%`;
    yearProgressBar.textContent = `${data.percentage}%`;
    yearProgressBar.setAttribute('aria-valuenow', data.percentage);
    yearProgressText.textContent = `Year ${data.current_year}/${data.total_years}`;
}

function handleArticleSaved(data) {
    console.log("Handling article saved:", data);
    // You can implement this if needed
}

// Function to stop the current search
function stopSearch() {
    console.log("Stopping search...");
    fetch('/api/search/stop', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
        .then(response => response.json())
        .then(data => {
            console.log('Stop search response:', data);
            if (data.status === 'stopped') {
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

// Update form submission handler to process the appropriate date inputs
document.getElementById('searchForm').addEventListener('submit', function (e) {
    e.preventDefault();
    console.log("Search form submitted");

    // Show the progress card
    progressCard.style.display = 'block';
    
    // Update UI to show search is in progress
    document.getElementById('searchBtn').disabled = true;
    document.getElementById('searchBtn').textContent = 'Searching...';
    document.getElementById('stopBtn').style.display = 'inline-block';
    document.getElementById('stopBtn').disabled = false;
    
    // Clear any previous logs
    logContainer.innerHTML = '<p class="log-entry text-info">Starting search...</p>';

    // Get form values
    const query = document.getElementById('query').value;
    const cantons = document.getElementById('cantons').value;
    const startFrom = document.getElementById('start_from') ? document.getElementById('start_from').value : '0';
    const maxArticles = document.getElementById('searches') ? document.getElementById('searches').value : 'all';
    const searchBy = document.getElementById('search_by').value;
    const correctionMethod = document.getElementById('correction_method').value;

    // Get date range values based on the selected search method
    let startYear, endYear, decade;
    if (searchBy === 'year') {
        startYear = document.getElementById('start_year').value;
        endYear = document.getElementById('end_year').value;
    } else if (searchBy === 'decade') {
        decade = document.getElementById('decade_select') ? document.getElementById('decade_select').value : '';
    }

    // Prepare data for the API call
    const data = {
        query: query,
        cantons: cantons,
        start_from: parseInt(startFrom) || 0,
        searches: maxArticles,
        search_by: searchBy,
        correction_method: correctionMethod
    };

    // Add date range or decade based on the search method
    if (searchBy === 'year' && startYear) {
        data.start_year = startYear;
    }
    if (searchBy === 'year' && endYear) {
        data.end_year = endYear;
    } else if (searchBy === 'decade' && decade) {
        const [decadeStart, decadeEnd] = decade.split('-');
        data.start_year = decadeStart;
        data.end_year = decadeEnd;
    }

    // Log the search parameters
    logContainer.innerHTML += `<p class="log-entry">Search query: ${query}</p>`;
    if (cantons) {
        logContainer.innerHTML += `<p class="log-entry">Cantons: ${cantons}</p>`;
    }
    if (searchBy === 'year') {
        logContainer.innerHTML += `<p class="log-entry">Year range: ${startYear || 'any'} to ${endYear || 'any'}</p>`;
    } else if (searchBy === 'decade' && decade) {
        logContainer.innerHTML += `<p class="log-entry">Decade: ${decade}</p>`;
    } else if (searchBy === 'all_time') {
        logContainer.innerHTML += `<p class="log-entry">Searching all time periods</p>`;
    }
    logContainer.innerHTML += `<p class="log-entry">Max articles: ${maxArticles}</p>`;
    logContainer.innerHTML += `<p class="log-entry">Starting from result #${startFrom}</p>`;
    logContainer.innerHTML += `<p class="log-entry">Correction method: ${correctionMethod}</p>`;
    
    // Scroll to the bottom of the log container
    logContainer.scrollTop = logContainer.scrollHeight;

    // Make the API call to start the search
    fetch('/api/search', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
        .then(response => response.json())
        .then(data => {
            console.log('Search API response:', data);
            if (data.status === 'started') {
                // The search has started successfully
                // The WebSocket connection will handle progress updates
                
                // Manually trigger the search_started event handler if needed
                if (!data.periods) {
                    // If the server didn't include periods, use a default
                    data.periods = ['Default'];
                }
                if (!data.total_tasks) {
                    // If the server didn't include total_tasks, use the tasks_count
                    data.total_tasks = data.tasks_count || 1;
                }
                
                // Call the handler directly with the data from the API response
                handleSearchStarted({
                    total_tasks: data.total_tasks,
                    periods: data.periods
                });
                
                logContainer.innerHTML += '<p class="log-entry text-success">Search started successfully</p>';
            } else {
                // There was an error starting the search
                logContainer.innerHTML += `<p class="log-entry text-danger">Error starting search: ${data.error || 'Unknown error'}</p>`;
                document.getElementById('searchBtn').disabled = false;
                document.getElementById('searchBtn').textContent = 'Search';
                document.getElementById('stopBtn').style.display = 'none';
            }
            logContainer.scrollTop = logContainer.scrollHeight;
        })
        .catch(error => {
            console.error('Error starting search:', error);
            logContainer.innerHTML += `<p class="log-entry text-danger">Error starting search: ${error}</p>`;
            document.getElementById('searchBtn').disabled = false;
            document.getElementById('searchBtn').textContent = 'Search';
            document.getElementById('stopBtn').style.display = 'none';
            logContainer.scrollTop = logContainer.scrollHeight;
        });
});

// Add event listener to the search_by dropdown
document.getElementById('search_by').addEventListener('change', function () {
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
});

document.addEventListener('DOMContentLoaded', function () {
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
});
