# Setting Up a Google Gemini API Key

This guide explains how to obtain and set up a Google Gemini API key for use with the double disclosure detection workflow.

## Prerequisites

- A Google account
- A Google Cloud project (you can create one for free)
- A payment method added to your Google Cloud account (though you get $300 free credits as a new user)

## Step 1: Create or Select a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click on the project dropdown at the top of the page.
3. Click "New Project" or select an existing project.
4. If creating a new project, enter a name and click "Create".

## Step 2: Enable the Generative Language API

1. In the Google Cloud Console, navigate to "APIs & Services" > "Library" from the left menu.
2. Search for "Generative Language API".
3. Click on the API result and then click "Enable".

## Step 3: Create an API Key

1. In the Google Cloud Console, navigate to "APIs & Services" > "Credentials" from the left menu.
2. Click "Create Credentials" and select "API key".
3. Your new API key will be displayed. Copy this key to a secure location.
4. (Optional but recommended) Click "Restrict Key" to limit the usage of this key to only the Generative Language API.

## Step 4: Secure Your API Key

Since API keys should be kept secure, follow these best practices:

1. Store your API key in a secure environment variable or configuration file that's not committed to version control.
2. For development purposes, you can create a `.gemini_api_key` file in your project root:

```bash
echo "YOUR_API_KEY" > .gemini_api_key
```

3. Add `.gemini_api_key` to your `.gitignore` file to prevent accidental commits.

## Step 5: Configure API Usage

The Gemini API has usage limits and quotas. To configure these:

1. In the Google Cloud Console, navigate to "APIs & Services" > "Quotas & System Limits".
2. Find "Generative Language API" and adjust quotas if needed.

## Step 6: Test Your API Key

You can test your API key using our test script:

```bash
python scripts/test_gemini_entity_workflow.py --api-key YOUR_API_KEY
```

Or with the API key file:

```bash
python scripts/test_gemini_entity_workflow.py --api-key-file .gemini_api_key
```

## Troubleshooting

### API Key Not Working

- Ensure the API key is correctly copied with no extra spaces or characters.
- Verify that the Generative Language API is enabled for your project.
- Check that your API key has permission to access the Generative Language API.

### Rate Limit Exceeded

- Gemini has rate limits for API requests. If you exceed these limits, your requests may be throttled.
- Our scripts include retry mechanisms with exponential backoff to handle rate limiting.
- You can adjust the delay between requests using the `--api-delay` parameter in our scripts.

### Billing Issues

- Ensure your billing account is active and has no payment issues.
- Monitor your usage in the Google Cloud Console under "Billing" to avoid unexpected charges.

## Cost Considerations

- Google provides $300 in free credits for new users.
- The Gemini API usage is charged based on input and output tokens.
- You can monitor and limit your costs by:
  - Setting budget alerts in Google Cloud Console
  - Using the `--batch-size` parameter to control how many entities are processed at once
  - Running test workflows on smaller datasets first

## Additional Resources

- [Official Google Generative AI documentation](https://ai.google.dev/docs)
- [Google Cloud billing documentation](https://cloud.google.com/billing/docs)
- [Gemini API pricing](https://ai.google.dev/pricing) 