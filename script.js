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
  function formatModelName(filename) {
    // Remove 'predictions_data_' prefix and '.json' suffix
    const modelName = filename.substring(16, filename.length - 5);
    // Split by hyphen and capitalize each part
    return modelName.split('-').map(part => 
      part.charAt(0).toUpperCase() + part.slice(1)
    ).join(' ');
  }

  // Define prediction files directly
  const files = ["predictions_data_gemini-1.5-pro.json"];
  console.log("Files to load:", files);
  
  let firstTab = null;
  files.forEach((file, index) => {
    console.log("Creating tab for file:", file);
    const $tab = $('<li>').append(
      $('<a>').html(`
        <span class="icon is-small"><i class="fas fa-robot"></i></span>
        <span>${formatModelName(file)}</span>
      `)
    ).on('click', () => loadData(file, $tab, index));
    
    $tabContainer.append($tab);
    if (index === 0) {
      firstTab = $tab;
    }
  });

  // Load first tab by default
  if (firstTab) {
    console.log("Loading first tab with file:", files[0]);
    loadData(files[0], firstTab, 0);
  } else {
    console.error("No first tab found!");
  }

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

        if (!data.categorized_predictions) {
          console.error("No categorized_predictions found in data");
          console.log("Available data structure:", JSON.stringify(data, null, 2));
          $tabContent.html('<div class="notification is-danger">Invalid data format: missing categorized_predictions</div>');
          return;
        }

        // Select the clicked tab
        $('.tabs li').removeClass('is-active');
        $tab.addClass('is-active');
        $tabContent.empty();

        const categorizedPredictions = data.categorized_predictions;
        const model = data.model || formatModelName(file);

        console.log("Model name:", model);
        console.log("Categories found:", Object.keys(categorizedPredictions));

        // Add model info section
        $tabContent.append(`
          <div class="box mb-5">
            <h2 class="title is-4">
              <span class="icon-text">
                <span class="icon"><i class="fas fa-robot"></i></span>
                <span>Model: ${model}</span>
              </span>
            </h2>
          </div>
        `);

        // Create the category sections
        for (const [category, clusters] of Object.entries(categorizedPredictions)) {
          console.log(`Processing category: ${category}, number of clusters: ${clusters?.length}`);
          const $categorySection = $('<section>').addClass('section pt-4');
          const $categoryContainer = $('<div>').addClass('container');
          
          // Add category header with appropriate color
          const categoryColor = {
            'Likely': 'is-success',
            'Maybe': 'is-info',
            'Unlikely': 'is-danger'
          }[category] || 'is-info';
          
          $categoryContainer.append(`
            <h2 class="title is-4 mb-5">
              <span class="icon-text">
                  <i class="fas ${category === 'Likely' ? 'fa-check-circle has-text-success' : 
                                category === 'Maybe' ? 'fa-question-circle has-text-info' : 
                                'fa-times-circle has-text-danger'}"></i> &nbsp;
                <span class="${category === 'Likely' ? 'has-text-success' : 
                             category === 'Maybe' ? 'has-text-info' : 
                             'has-text-danger'}">${category} Predictions</span>
              </span>
            </h2>
          `);

          if (clusters && clusters.length > 0) {
            clusters.forEach(cluster => {
              const $themeCard = $('<div>')
                .addClass(`card mb-4 theme-card ${categoryColor}`)
                .appendTo($categoryContainer);
              const $cardHeader = $('<header>').addClass('card-header');
              const $cardContent = $('<div>').addClass('card-content is-hidden');

              // Add theme header
              $cardHeader.html(`
                <div class="card-header-title">
                  ${cluster.theme}
                  <span class="prediction-count ml-2">${cluster.predictions.length} predictions</span>
                </div>
                <button class="card-header-icon">
                  <span class="icon">
                    <i class="fas fa-angle-down"></i>
                  </span>
                </button>
              `);

              // Add theme summary and predictions
              const $predictionsContent = $('<div>').addClass('content');
              if (cluster.theme_summary) {
                $predictionsContent.append(`
                  <div class="notification ${categoryColor} is-light mb-4">
                    <div class="summary-header">TL;DR:</div>
                    <div class="summary-content">${cluster.theme_summary}</div>
                  </div>
                `);
              }

              // Sort and add predictions
              cluster.predictions
                .sort((a, b) => parseFloat(b.probability) - parseFloat(a.probability))
                .forEach(prediction => {
                  const probability = parseFloat(prediction.probability);
                  const confidenceClass = probability >= 0.7 ? 'is-success' : 
                                        probability >= 0.3 ? 'is-info' : 
                                        'is-danger';
                  
                  $predictionsContent.append(`
                    <div class="prediction-box mb-4">
                      <div class="prediction-content">
                        <div class="prediction-header">
                          <div class="prediction-text">
                            <span class="icon-text">
                              <span class="has-text-weight-medium"><i class="prediction-icon fas fa-user"></i> ${prediction.prediction}</span>
                            </span>
                          </div>
                          <div class="prediction-probability ${confidenceClass}">
                            <span class="icon"><i class="fas fa-chart-line"></i></span>
                            <span>${(probability * 100).toFixed(0)}%</span>
                          </div>
                        </div>
                        <div class="prediction-justification ${confidenceClass}">
                          <span class="icon-text">
                            <span><i class="fas fa-robot"></i> &nbsp;${prediction.justification}</span>
                          </span>
                        </div>
                      </div>
                    </div>
                  `);
                });

              $cardContent.append($predictionsContent);
              $themeCard.append($cardHeader, $cardContent);
              
              // Add click handler
              $cardHeader.on('click', () => {
                $cardContent.toggleClass('is-hidden');
                $cardHeader.find('.fa-angle-down').toggleClass('fa-rotate-180');
              });
            });
          } else {
            $categoryContainer.append(`
              <div class="notification is-light">
                <span class="icon-text">
                  <span class="icon"><i class="fas fa-info-circle"></i></span>
                  <span>No predictions in this category.</span>
                </span>
              </div>
            `);
          }
          
          $categorySection.append($categoryContainer);
          $tabContent.append($categorySection);
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
});