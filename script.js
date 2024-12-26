let loaded = false;
let modelsData = {};  // Store all models' data
let $tabContent;  // Global reference to tab content

// Function to load theme predictions
function loadThemePredictions(theme, $targetContent) {
  $targetContent.empty();
  const $themeContainer = $('<div class="container"></div>');

  // Add probability filters at the top
  const filterTemplate = document.getElementById('probability-filters');
  const $filters = $(filterTemplate.content.cloneNode(true));
  $themeContainer.append($filters);

  $themeContainer.append(`
    <h2 class="title is-4 mb-5">
      <span class="icon-text">
        <span>${theme.theme}</span>
      </span>
    </h2>
  `);

  if (theme.summary) {
    $themeContainer.append(`
      <div class="notification is-light mb-4">
        <div class="summary-content"><strong>Summary:</strong> ${theme.summary}</div>
      </div>
    `);
  }

  if (theme.predictions && theme.predictions.length > 0) {
    theme.predictions.forEach(prediction => {
      const probability = parseFloat(prediction.probability);
      const confidenceClass = probability >= 0.7 ? 'is-success' :
        probability >= 0.3 ? 'is-info' :
          'is-danger';
      const probabilityCategory = probability >= 0.7 ? 'likely' :
        probability >= 0.3 ? 'maybe' : 'unlikely';

      const $predictionBox = $('<div>')
        .addClass(`prediction-box mb-4 ${confidenceClass}`)
        .attr('data-probability', probabilityCategory)
        .appendTo($themeContainer);

      $predictionBox.html(`
        <div class="prediction-content">
          <div class="prediction-header">
            <div class="prediction-text">
              <span class="icon-text">
                <span class="has-text-weight-medium">
                  <i class="prediction-icon fas fa-user"></i> ${prediction.prediction}
                </span>
              </span>
            </div>
            <div class="prediction-probability ${confidenceClass}">
              <span class="icon"><i class="fas fa-chart-line"></i></span>
              <span>${(probability * 100).toFixed(0)}%</span>
            </div>
          </div>
          <div class="prediction-justification ${confidenceClass}">
            <span class="icon-text">
              <span><i class="fas fa-robot"></i> ${prediction.justification}</span>
            </span>
          </div>
        </div>
      `);
    });

    // Handle filter clicks
    $themeContainer.find('.probability-filters .button').on('click', function () {
      const $button = $(this);
      const filter = $button.data('filter');

      // Update button states
      $button.siblings().removeClass('is-selected');
      $button.addClass('is-selected');

      // Filter predictions
      const $predictions = $themeContainer.find('.prediction-box');
      if (filter === 'all') {
        $predictions.show();
      } else {
        $predictions.each(function () {
          const $prediction = $(this);
          const probability = $prediction.data('probability');
          if (probability === filter) {
            $prediction.show();
          } else {
            $prediction.hide();
          }
        });
      }
    });
  } else {
    $themeContainer.append(`
      <div class="notification is-light">
        <span class="icon-text">
          <span class="icon"><i class="fas fa-info-circle"></i></span>
          <span>No predictions found in this theme.</span>
        </span>
      </div>
    `);
  }

  $targetContent.append($themeContainer);
}

// Function to setup the theme UI
function setupThemeUI(sortedThemes, model) {
  $tabContent.empty();

  const $tabContentContainer = $('<div class="columns is-variable is-1 is-gapless" style="min-height: 500px"></div>').appendTo($tabContent);
  const $sidebar = $('<aside class="column is-one-quarter menu theme-sidebar is-scrollable" style="height: 500px; overflow-y: auto"></aside>').appendTo($tabContentContainer);
  const $mainContent = $('<div class="column is-three-quarters prediction-column is-scrollable" style="height: 500px; overflow-y: auto"></div>').appendTo($tabContentContainer);

  $sidebar.append(`
    <div class="box mb-5">
      <h2 class="title is-4">
        <span class="icon-text">
          <span><i class="fas fa-robot"></i>&nbsp;${model}</span>
        </span>
      </h2>
      <div class="legend flex is-flex-wrap-wrap is-justify-content-space-between">
        <span class="legend-item"><i class="fas fa-square has-text-success mr-2"></i>Likely</span>
        <span class="legend-item"><i class="fas fa-square has-text-info ml-2 mr-2"></i>Maybe</span>
        <span class="legend-item"><i class="fas fa-square has-text-danger ml-2 mr-2"></i>Unlikely</span>
      </div>
    </div>
  `);

  const $themeMenu = $('<ul class="menu-list"></ul>').appendTo($sidebar);

  // Create the theme navigation
  sortedThemes.forEach(theme => {
    let predictionCount = 0;
    if (theme.predictions && Array.isArray(theme.predictions)) {
      predictionCount = theme.predictions.length;
    }
    const $themeItem = $('<li class="theme-list-item"></li>').append(
      '<a class="theme-link" href="#">' + theme.theme +
      ' <span class="tag is-light is-small ml-2">' + predictionCount + ' Predictions</span></a>'
    ).on('click', function (event) {
      event.preventDefault();
      $themeMenu.find('li').removeClass('is-active');
      $(this).addClass('is-active');

      $mainContent.animate({ scrollTop: 0 }, 200, () => {
        loadThemePredictions(theme, $mainContent);
      });
    });

    $themeMenu.append($themeItem);
  });

  if (sortedThemes.length > 0) {
    loadThemePredictions(sortedThemes[0], $mainContent);
    $themeMenu.find('li').first().addClass('is-active');
  }
}

// Function to load data for a specific model
function loadData(file, $tab, tabIndex) {
  // Show loading state
  $tabContent.html(`
    <div class="has-text-centered p-6">
      <span class="icon is-large">
        <i class="fas fa-spinner fa-pulse fa-2x"></i>
      </span>
      <p class="mt-2">Loading predictions...</p>
    </div>
  `);

  fetch(file)
    .then(response => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return response.text();
    })
    .then(text => {
      try {
        const data = JSON.parse(text);
        // Store the model data
        modelsData[data.model] = data;
        return data;
      } catch (e) {
        console.error("Error parsing JSON:", e);
        throw e;
      }
    })
    .then(data => processModelData(data, $tab))
    .catch(error => {
      console.error('Error in data loading process:', error);
      console.error('Error stack:', error.stack);
      $tabContent.html(`
        <div class="notification is-danger">
          <span class="icon-text">
            <span class="icon"><i class="fas fa-exclamation-triangle"></i></span>
            <span>Error loading predictions: ${error.message}</span>
          </span>
        </div>
      `);
    });
}

// Function to process model data after loading
function processModelData(data, $tab) {
  if (!data) {
    console.error("No data available");
    $tabContent.html('<div class="notification is-danger">Error loading data</div>');
    return;
  }

  if (!data.themes) {
    console.error("No themes found in data");
    $tabContent.html('<div class="notification is-danger">Invalid data format: missing categorized_predictions</div>');
    return;
  }

  // Select the clicked tab
  $('.tabs li').removeClass('is-active');
  $tab.addClass('is-active');
  $tabContent.empty();

  const themes = data.themes;
  const model = data.model || formatModelName(file);

  // Combine all "Other" themes into one
  const otherThemes = themes.filter(theme => theme.theme === "Other");
  const nonOtherThemes = themes.filter(theme => theme.theme !== "Other");

  if (otherThemes.length > 0) {
    const combinedOther = {
      theme: "Other",
      summary: "Other miscellaneous predictions that don't fit into the main categories.",
      predictions: otherThemes.reduce((acc, theme) => acc.concat(theme.predictions), [])
    };
    nonOtherThemes.push(combinedOther);
  }

  const sortedThemes = [...nonOtherThemes].sort((a, b) => {
    if (a.theme === "Other") return 1;
    if (b.theme === "Other") return -1;
    const countA = a.predictions ? a.predictions.length : 0;
    const countB = b.predictions ? b.predictions.length : 0;
    return countB - countA;
  });

  setupThemeUI(sortedThemes, model);
}

$(window).on('load', () => {
  if (loaded) {
    return;
  }
  loaded = true;

  const $tabContainer = $('.tabs .tabs-ul');
  $tabContent = $('#tab-content');

  // Function to format model name for display
  function formatModelName(modelName) {
    return modelName.split('_').map(part =>
      part.charAt(0).toUpperCase() + part.slice(1)
    ).join(' ');
  }

  // Function to fetch all files from the output directory and filter for .json files
  function fetchFilesFromDirectory() {
    return [
      "outputs/predictions_data_gemini-1.5-pro.json",
      "outputs/predictions_data_claude-3.5-sonnet-20241022.json",
      "outputs/predictions_data_gpt-4-turbo-preview.json",
      "outputs/predictions_data_gpt-4o.json",
    ];
  }

  // Function to fetch data and create tab
  function createTabFromFile(file, index) {
    fetch(file)
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.text();
      })
      .then(text => {
        try {
          const data = JSON.parse(text);
          const modelName = data.model;


          const $tab = $('<li>').append(
            $('<a>').html(`
              <span class="icon is-small"><i class="fas fa-robot"></i></span>
              <span>${formatModelName(modelName)}</span>
            `)
          ).on('click', () => loadData(file, $tab, index));

          $tabContainer.append($tab);
          return $tab;
        } catch (e) {
          console.error(`Error parsing JSON for file: ${file}`, e);
        }
      })
      .catch(error => {
        console.error(`Error fetching file: ${file}`, error);
      });
  }

  // Get files from output directory
  const filesFromOutput = fetchFilesFromDirectory();

  // Preload all model data
  const preloadPromises = filesFromOutput.map(file => {
    return fetch(file)
      .then(response => response.json())
      .then(data => {
        modelsData[data.model] = data;
        return data;
      })
      .catch(error => {
        console.error(`Error preloading data for ${file}:`, error);
      });
  });

  // Ensure we have files to load
  Promise.all(preloadPromises).then(() => {
    if (filesFromOutput.length > 0) {
      filesFromOutput.forEach((file, index) => {
        createTabFromFile(file, index);
      });

      // Load the first tab's data
      const firstFile = filesFromOutput[0];
      fetch(firstFile)
        .then(response => response.json())
        .then(data => {
          const firstTab = $('.tabs li').first();
          loadData(firstFile, firstTab, 0);
        })
        .catch(error => {
          console.error('Error loading first tab:', error);
        });
    } else {
      console.error("No JSON files found in the outputs directory");
      $('.tabs-ul').append('<li class="is-danger">No prediction files found</li>');
    }

    // Add statistics tab
    const $statsTab = $('<li>').append(
      $('<a>').html(`
        <span class="icon is-small"><i class="fas fa-chart-bar"></i></span>
        <span>Statistics</span>
      `)
    ).on('click', () => loadStatistics());

    $tabContainer.append($statsTab);

    function loadStatistics() {
      $('.tabs li').removeClass('is-active');
      $statsTab.addClass('is-active');

      const statsTemplate = document.getElementById('statistics-template');
      const $stats = $(statsTemplate.content.cloneNode(true));
      const $modelsStats = $stats.find('.models-stats');

      // Create rows for 2x2 grid
      let currentRow;
      Object.entries(modelsData).forEach(([modelName, data], index) => {
        if (index % 2 === 0) {
          currentRow = $('<div class="columns is-desktop"></div>');
          $modelsStats.append(currentRow);
        }

        const predictions = data.themes.flatMap(theme => theme.predictions);
        const themes = data.themes.filter(theme => theme.theme !== "Other").length;

        // Calculate probability distributions
        const likelyCount = predictions.filter(p => p.probability >= 0.7).length;
        const maybeCount = predictions.filter(p => p.probability >= 0.3 && p.probability < 0.7).length;
        const unlikelyCount = predictions.filter(p => p.probability < 0.3).length;
        const total = predictions.length;

        const $modelStats = $(`
          <div class="column is-half">
            <div class="box mb-4">
              <h3 class="title is-5">${formatModelName(modelName)}</h3>
              <div class="content">
                <p><strong>Total Predictions:</strong> ${total}</p>
                <p><strong>Number of Themes:</strong> ${themes}</p>
                <div class="mb-2"><strong>Probability Distribution:</strong></div>
                <div class="probability-bars">
                  <div class="columns is-gapless mb-1">
                    <div class="column is-2">Likely</div>
                    <div class="column">
                      <div class="probability-bar" style="background-color: #48c78e; width: ${(likelyCount / total * 100)}%">
                        ${likelyCount} (${Math.round(likelyCount / total * 100)}%)
                      </div>
                    </div>
                  </div>
                  <div class="columns is-gapless mb-1">
                    <div class="column is-2">Maybe</div>
                    <div class="column">
                      <div class="probability-bar" style="background-color: #485fc7; width: ${(maybeCount / total * 100)}%">
                        ${maybeCount} (${Math.round(maybeCount / total * 100)}%)
                      </div>
                    </div>
                  </div>
                  <div class="columns is-gapless">
                    <div class="column is-2">Unlikely</div>
                    <div class="column">
                      <div class="probability-bar" style="background-color: #f14668; width: ${(unlikelyCount / total * 100)}%">
                        ${unlikelyCount} (${Math.round(unlikelyCount / total * 100)}%)
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        `);
        currentRow.append($modelStats);
      });

      $tabContent.empty().append($stats);
    }
  });
});