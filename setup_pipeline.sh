#!/bin/bash

# Setup script for the complete parliamentary disclosure processing pipeline
# This script sets up the data standardization steps and integrates them with the main processing script

set -e  # Exit on error

echo "Setting up the complete parliamentary disclosure processing pipeline..."

# Apply patch to process_parliament_disclosures.py
echo "Updating process_parliament_disclosures.py with standardization support..."
if [ -f "process_mp.patch" ]; then
    # Apply the patch if it exists
    patch -p0 < process_mp.patch
    if [ $? -eq 0 ]; then
        echo "Successfully applied patch to process_parliament_disclosures.py"
    else
        echo "Failed to apply patch. Making manual changes..."
        # Manually update the file if the patch fails
        sed -i 's/requests_per_day: int = 1500,/requests_per_day: int = 1500,\n    standardize: bool = False,/' process_parliament_disclosures.py
        sed -i 's/requests_per_day: API rate limit in requests per day/requests_per_day: API rate limit in requests per day\n        standardize: Whether to run data standardization after processing/' process_parliament_disclosures.py
        sed -i 's/parser.add_argument("--continue-on-error", action="store_true", help="Continue processing if an error occurs")/parser.add_argument("--continue-on-error", action="store_true", help="Continue processing if an error occurs")\n    parser.add_argument("--standardize", action="store_true", help="Run data standardization after processing")/' process_parliament_disclosures.py
        sed -i 's/requests_per_day=args.rpd/requests_per_day=args.rpd,\n            standardize=args.standardize/' process_parliament_disclosures.py
    fi
else
    echo "Patch file not found. Making manual changes..."
    # Manually update the file
    sed -i 's/requests_per_day: int = 1500,/requests_per_day: int = 1500,\n    standardize: bool = False,/' process_parliament_disclosures.py
    sed -i 's/requests_per_day: API rate limit in requests per day/requests_per_day: API rate limit in requests per day\n        standardize: Whether to run data standardization after processing/' process_parliament_disclosures.py
    sed -i 's/parser.add_argument("--continue-on-error", action="store_true", help="Continue processing if an error occurs")/parser.add_argument("--continue-on-error", action="store_true", help="Continue processing if an error occurs")\n    parser.add_argument("--standardize", action="store_true", help="Run data standardization after processing")/' process_parliament_disclosures.py
    sed -i 's/requests_per_day=args.rpd/requests_per_day=args.rpd,\n            standardize=args.standardize/' process_parliament_disclosures.py
fi

# Add standardization code to the end of the processing function
echo "Adding standardization code to process_parliament_disclosures.py..."
STANDARDIZE_CODE='
    # Run data standardization if requested
    if standardize and store_in_db:
        logger.info("\n" + "="*80)
        logger.info("RUNNING DATA STANDARDIZATION")
        logger.info("="*80)
        
        try:
            import standardize_data
            standardize_data.standardize_database(db_path=db_path)
            
            # Run category validation and update
            logger.info("\n" + "="*80)
            logger.info("RUNNING CATEGORY VALIDATION")
            logger.info("="*80)
            
            import update_categories
            update_categories.update_categories(db_path=db_path)
        except Exception as e:
            logger.error(f"Error during data standardization: {str(e)}")
            logger.error("Standardization failed, but processing was completed successfully")
    elif standardize and not store_in_db:
        logger.warning("Standardization can only be run when storing data in the database (--store-in-db)")
'

# Check if the standardization code is already in the file
if ! grep -q "RUNNING DATA STANDARDIZATION" process_parliament_disclosures.py; then
    # Find the line containing "Full statistics saved to: {stats_path}" and add the code after it
    sed -i '/Full statistics saved to: {stats_path}/a '"$STANDARDIZE_CODE"'' process_parliament_disclosures.py
    echo "Added standardization code to process_parliament_disclosures.py"
else
    echo "Standardization code already exists in process_parliament_disclosures.py"
fi

# Verify that the files exist
echo "Verifying that all required files exist..."

FILES_TO_CHECK=("standardize_mp_names.py" "standardize_electorates.py" "standardize_data.py")

for file in "${FILES_TO_CHECK[@]}"; do
    if [ -f "$file" ]; then
        echo "✓ $file exists"
    else
        echo "✗ $file does not exist"
        exit 1
    fi
done

echo "All required files exist!"

echo "Setup complete! You can now run the following command to process parliaments with standardization:"
echo "python process_parliament_disclosures.py --all --store-in-db --skip-scraping --rpm 10 --continue-on-error --standardize"
echo ""
echo "The --standardize flag will run the standardization steps after processing to ensure consistent MP names and electorates." 