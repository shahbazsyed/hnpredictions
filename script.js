let loaded = false;
$(window).on('load', () => {
  console.log("Window loaded");
  if (loaded) {
    console.log("already loaded, exiting")
    return;
  }
  loaded = true;

  const $tabContainer = $('.tabs .tabs-ul');
  const $tabContent = $('#tab-content');

  // Function to format model name for display
  function formatModelName(modelName) {
    // Split by hyphen and capitalize each part
    return modelName.split('_').map(part =>
      part.charAt(0).toUpperCase() + part.slice(1)
    ).join(' ');
  }

  // Function to fetch all files from the output directory and filter for .json files
  function fetchFilesFromDirectory() {
    // Since we can't do real globbing with client-side JavaScript we will use a simulated list from the output directory
    const files = [
      "outputs/predictions_data_gemini-1.5-pro.json",
      "outputs/predictions_data_claude-3.5-sonnet-20241022.json",
      "outputs/predictions_data_gpt-4-turbo-preview.json",
      "outputs/predictions_data_gpt-4o.json",
    ];
    return files.filter(file => file.endsWith(".json"));
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

          console.log("Creating tab for file:", file, "Model Name:", modelName);

          const $tab = $('<li>').append(
            $('<a>').html(`
                          <span class="icon is-small"><i class="fas fa-robot"></i></span>
                          <span>${formatModelName(modelName)}</span>
                        `)
          ).on('click', () => loadData(file, $tab, index));

          $tabContainer.append($tab);
          if (index === 0) {
            firstTab = $tab;
          }
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
  console.log("Files found:", filesFromOutput)

  // Add tab-content class to the content container
  $tabContent.addClass('tab-content');

  // Create tabs dynamically
  filesFromOutput.forEach((file, index) => {
    createTabFromFile(file, index);
  });


  // Load first tab by default
  setTimeout(() => {
    if (firstTab) {
      console.log("Loading first tab with file:", `/outputs/${filesFromOutput[0]}`);
      loadData(`/outputs/${filesFromOutput[0]}`, firstTab, 0);
    } else {
      console.error("No first tab found!");
    }
  }, 100);


  function loadData(file, $tab, tabIndex) {
    console.log("=== Starting to load data ===");
    console.log("Loading file:", file);
    console.log("Tab index:", tabIndex);

    // Show loading state
    $tabContent.html(`
      <div class="has-text-centered p-6">
        <span class="icon is-large">
          <i class="fas fa-spinner fa-pulse fa-2x"></i>
        </span>
        <p class="mt-2">Loading predictions...</p>
      </div>
    `);

    // Let's also check if the file exists first
    fetch(file)
      .then(response => {
        console.log("Response status:", response.status);
        console.log("Response headers:", response.headers);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.text();  // First get as text to see the raw response
      })
      .then(text => {
        console.log("Raw response text:", text.substring(0, 500) + "..."); // Show first 500 chars
        try {
          const data = JSON.parse(text);
          console.log("Successfully parsed JSON data:", data);
          return data;
        } catch (e) {
          console.error("Error parsing JSON:", e);
          throw e;
        }
      })
      .then(data => {
        console.log("=== Processing parsed data ===");
        console.log("Full data object:", data);
        console.log("Keys in data:", Object.keys(data));

        if (!data) {
          console.error("No data available");
          $tabContent.html('<div class="notification is-danger">Error loading data</div>');
          return;
        }

        if (!data.themes) {
          console.error("No themes found in data");
          console.log("Available data structure:", JSON.stringify(data, null, 2));
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

        const $tabContentContainer = $('<div class="columns is-variable is-1 is-gapless" style="min-height: 500px"></div>').appendTo($tabContent);
        const $sidebar = $('<aside class="column is-one-quarter menu theme-sidebar is-scrollable" style="height: 500px; overflow-y: auto"></aside>').appendTo($tabContentContainer);
        const $mainContent = $('<div class="column is-three-quarters prediction-column is-scrollable" style="height: 500px; overflow-y: auto"></div>').appendTo($tabContentContainer);

        $sidebar.append(`
                    <div class="box mb-5">
                        <h2 class="title is-4">
                          <span class="icon-text">
                            <span class="icon"><i class="fas fa-robot"></i></span>
                            <span>Model: ${model}</span>
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
          const $themeItem = $('<li class="theme-list-item"></li>').append('<a class="theme-link" href="#">' + theme.theme + ' <span class="tag is-light is-small ml-2">' + predictionCount + ' Predictions</span></a>')
            .on('click', function (event) {
              event.preventDefault();
              console.log(`Loading predictions for theme: ${theme.theme}`);
              $themeMenu.find('li').removeClass('is-active');
              $(this).parent('li').addClass('is-active');

              $mainContent.animate({ scrollTop: 0 }, 200, () => {
                loadThemePredictions(theme, $mainContent);
              });
            }).appendTo($themeMenu);
        });

        if (sortedThemes.length > 0) {
          loadThemePredictions(sortedThemes[0], $mainContent);
          $themeMenu.find('li').first().addClass("is-active")
        }
      })
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


  function loadThemePredictions(theme, $targetContent) {
    $targetContent.empty();
    console.log("Loading Theme:", theme)
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
                  <div class="summary-content"><strong>Summary:</strong>  ${theme.summary}</div>
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
                                 <span class="has-text-weight-medium"><i class="prediction-icon fas fa-user"></i>  ${prediction.prediction}</span>
                               </span>
                              </div>
                             <div class="prediction-probability ${confidenceClass}">
                             <span class="icon"><i class="fas fa-chart-line"></i></span>
                             <span>${(probability * 100).toFixed(0)}%</span>
                             </div>
                             </div>
                            <div class="prediction-justification ${confidenceClass}">
                             <span class="icon-text">
                               <span><i class="fas fa-robot"></i>  ${prediction.justification}</span>
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
});