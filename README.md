# Test Task

A high-performance, async Gmail API client that efficiently fetches user profile, labels, and recent emails while transforming verbose Gmail API responses into clean, essential data structures suitable for AI agent processing.

## Features

- **Async/Concurrent Processing**: Fetch profile, labels, and emails simultaneously for maximum speed
- **Data Transformation**: Transform verbose Gmail API responses into clean, essential fields only
- **Type Safety**: Full type hints and TypedDict definitions for all data structures
- **Error Handling**: Comprehensive error handling with custom exceptions
- **Test Coverage**: Extensive unit tests covering normal and edge cases
- **PEP8 Compliant**: Follows Python coding standards and best practices

## Essential Fields Extracted

The client transforms Gmail messages to include only these essential fields:

```python
GMAIL_FIELDS = [
    "messageId",
    "threadId",
    "messageTimestamp",
    "labelIds",
    "sender",
    "subject",
    "messageText",
]
```

## Installation

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set up Gmail API credentials:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the Gmail API
   - Create OAuth2 credentials
   - Download the credentials JSON file

## Usage

### Basic Usage

```python
import asyncio
from google.oauth2.credentials import Credentials
from gmail_client import fetch_gmail_data, AsyncGmailClient

async def main():
    # Initialize credentials (replace with your actual credentials)
    credentials = Credentials(
        token='your_access_token',
        refresh_token='your_refresh_token',
        token_uri='https://oauth2.googleapis.com/token',
        client_id='your_client_id',
        client_secret='your_client_secret'
    )

    # Fetch all data concurrently (recommended)
    data = await fetch_gmail_data(credentials, max_emails=10)

    print(f"Profile: {data['profile']}")
    print(f"Labels count: {len(data['labels'])}")
    print(f"Recent emails count: {len(data['emails'])}")

    # Print first email details
    if data['emails']:
        email = data['emails'][0]
        print(f"First email from: {email['sender']}")
        print(f"Subject: {email['subject']}")

# Run the async function
asyncio.run(main())
```

### Advanced Usage with Individual Methods

```python
async def advanced_usage():
    credentials = get_credentials()  # Your credential loading function
    client = AsyncGmailClient(credentials)

    # Fetch individual components
    profile = await client.get_profile()
    labels = await client.get_labels()
    emails = await client.get_recent_emails(max_results=20)

    # Process results
    print(f"User: {profile['emailAddress']}")
    print(f"Total messages: {profile['messagesTotal']}")

    for label in labels:
        print(f"Label: {label['name']} ({label['type']})")

    for email in emails:
        print(f"Email: {email['subject']} from {email['sender']}")
```

## Data Structures

### GmailMessage

```python
class GmailMessage(TypedDict):
    messageId: str
    threadId: str
    messageTimestamp: str  # ISO format datetime
    labelIds: List[str]
    sender: str
    subject: str
    messageText: str
```

### GmailProfile

```python
class GmailProfile(TypedDict):
    emailAddress: str
    messagesTotal: int
    threadsTotal: int
    historyId: str
```

### GmailLabel

```python
class GmailLabel(TypedDict):
    id: str
    name: str
    type: str  # 'system' or 'user'
```

## Architecture and Design

### Async Concurrency

The client uses Python's `asyncio` with `concurrent.futures.ThreadPoolExecutor` to handle the Gmail API's synchronous nature while maintaining async benefits. All three main operations (profile, labels, emails) run concurrently for optimal performance.

### Data Transformation Logic

The transformation process:

1. **Message Processing**: Extracts essential headers (From, Subject) from the verbose header array
2. **Content Extraction**: Recursively processes multipart MIME structures to extract plain text content
3. **Timestamp Conversion**: Converts Gmail's internal timestamp to ISO format
4. **Field Normalization**: Provides default values for missing optional fields

### Error Handling

- Custom `GmailAPIError` exception for API-related errors
- Graceful handling of missing or malformed data
- Automatic credential refresh when needed

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
pytest test_gmail_client.py -v

# Run with coverage
pytest test_gmail_client.py --cov=gmail_client --cov-report=html

# Run specific test scenarios
pytest test_gmail_client.py::TestAsyncGmailClient::test_transform_message_complete -v
pytest test_gmail_client.py::TestAsyncGmailClient::test_transform_message_incomplete -v
```

### Test Scenarios Covered

1. **Normal Payload**: Complete Gmail message with all fields present
2. **Missing Fields**: Message with missing optional fields (subject, labelIds)
3. **Malformed Data**: Handling of corrupted or incomplete API responses
4. **Multipart Content**: Extraction from complex MIME structures
5. **API Errors**: Network and authentication error handling
6. **Concurrent Operations**: Testing async/await functionality

## Performance Considerations

- **Concurrent Fetching**: Profile, labels, and emails are fetched simultaneously
- **Efficient Encoding**: Base64 content is decoded only once per message
- **Memory Optimization**: Only essential fields are retained in memory
- **Connection Reuse**: Single service instance for multiple API calls

## Error Scenarios

The client handles various error conditions:

- **Authentication Errors**: Automatic token refresh
- **API Rate Limits**: Proper exception propagation
- **Network Issues**: Timeout and connection error handling
- **Malformed Responses**: Graceful degradation with default values
- **Missing Content**: Empty string defaults for text content
