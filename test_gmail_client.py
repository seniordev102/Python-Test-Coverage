"""Unit tests for the Gmail API client."""

import asyncio
import json
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from gmail_client import (
    AsyncGmailClient,
    GmailMessage,
    GmailProfile,
    GmailLabel,
    GmailAPIError,
    fetch_gmail_data,
    GMAIL_FIELDS
)


class TestAsyncGmailClient:
    """Test suite for AsyncGmailClient."""

    @pytest.fixture
    def mock_credentials(self):
        """Mock Google credentials."""
        credentials = Mock()
        credentials.expired = False
        credentials.refresh_token = None
        return credentials

    @pytest.fixture
    def gmail_client(self, mock_credentials):
        """Create Gmail client instance for testing."""
        return AsyncGmailClient(mock_credentials)

    @pytest.fixture
    def sample_complete_message(self):
        """Sample Gmail message with all fields present."""
        return {
            'id': 'msg123',
            'threadId': 'thread456',
            'internalDate': '1699123200000',  # Nov 4, 2023
            'labelIds': ['INBOX', 'UNREAD'],
            'payload': {
                'headers': [
                    {'name': 'From', 'value': 'sender@example.com'},
                    {'name': 'Subject', 'value': 'Test Email Subject'},
                    {'name': 'Date', 'value': 'Sat, 4 Nov 2023 12:00:00 +0000'}
                ],
                'mimeType': 'text/plain',
                'body': {
                    'data': 'VGhpcyBpcyBhIHRlc3QgZW1haWwgbWVzc2FnZS4='  # base64: "This is a test email message."
                }
            }
        }

    @pytest.fixture
    def sample_incomplete_message(self):
        """Sample Gmail message with missing optional fields."""
        return {
            'id': 'msg789',
            'threadId': 'thread012',
            'internalDate': '1699123200000',
            'payload': {
                'headers': [
                    {'name': 'From', 'value': 'another@example.com'},
                    # Missing Subject header
                ],
                'mimeType': 'multipart/mixed',
                'parts': [
                    {
                        'mimeType': 'text/plain',
                        'body': {
                            'data': 'SGVsbG8gd29ybGQh'  # base64: "Hello world!"
                        }
                    }
                ]
            }
            # Missing labelIds
        }

    @pytest.fixture
    def sample_profile(self):
        """Sample Gmail profile data."""
        return {
            'emailAddress': 'user@example.com',
            'messagesTotal': 1500,
            'threadsTotal': 750,
            'historyId': 'hist123456'
        }

    @pytest.fixture
    def sample_labels(self):
        """Sample Gmail labels data."""
        return {
            'labels': [
                {
                    'id': 'INBOX',
                    'name': 'INBOX',
                    'type': 'system',
                    'messageListVisibility': 'show',
                    'labelListVisibility': 'labelShow'
                },
                {
                    'id': 'Label_1',
                    'name': 'Work',
                    'type': 'user'
                }
            ]
        }

    def test_gmail_fields_constant(self):
        """Test that GMAIL_FIELDS contains expected fields."""
        expected_fields = [
            "messageId",
            "threadId",
            "messageTimestamp",
            "labelIds",
            "sender",
            "subject",
            "messageText",
        ]
        assert GMAIL_FIELDS == expected_fields

    def test_init(self, mock_credentials):
        """Test Gmail client initialization."""
        client = AsyncGmailClient(mock_credentials)
        assert client.credentials == mock_credentials
        assert client.service is None

    def test_extract_header_value(self, gmail_client):
        """Test header value extraction."""
        headers = [
            {'name': 'From', 'value': 'test@example.com'},
            {'name': 'Subject', 'value': 'Test Subject'},
            {'name': 'Date', 'value': '2023-11-04'}
        ]
        
        assert gmail_client._extract_header_value(headers, 'From') == 'test@example.com'
        assert gmail_client._extract_header_value(headers, 'subject') == 'Test Subject'  # case insensitive
        assert gmail_client._extract_header_value(headers, 'NonExistent') == ''

    def test_extract_email_content_plain_text(self, gmail_client):
        """Test email content extraction from plain text message."""
        payload = {
            'mimeType': 'text/plain',
            'body': {
                'data': 'VGVzdCBtZXNzYWdl'  # base64: "Test message"
            }
        }
        
        content = gmail_client._extract_email_content(payload)
        assert content == 'Test message'

    def test_extract_email_content_multipart(self, gmail_client):
        """Test email content extraction from multipart message."""
        payload = {
            'mimeType': 'multipart/mixed',
            'parts': [
                {
                    'mimeType': 'text/plain',
                    'body': {
                        'data': 'TXVsdGlwYXJ0IG1lc3NhZ2U='  # base64: "Multipart message"
                    }
                }
            ]
        }
        
        content = gmail_client._extract_email_content(payload)
        assert content == 'Multipart message'

    def test_extract_email_content_empty(self, gmail_client):
        """Test email content extraction with no content."""
        payload = {
            'mimeType': 'text/plain',
            'body': {}
        }
        
        content = gmail_client._extract_email_content(payload)
        assert content == ''

    def test_transform_message_complete(self, gmail_client, sample_complete_message):
        """Test message transformation with all fields present."""
        transformed = gmail_client._transform_message(sample_complete_message)
        
        assert isinstance(transformed, dict)
        assert transformed['messageId'] == 'msg123'
        assert transformed['threadId'] == 'thread456'
        # Check that timestamp is valid ISO format (timezone may vary)
        assert transformed['messageTimestamp'].startswith('2023-11-')
        assert 'T' in transformed['messageTimestamp']
        assert transformed['labelIds'] == ['INBOX', 'UNREAD']
        assert transformed['sender'] == 'sender@example.com'
        assert transformed['subject'] == 'Test Email Subject'
        assert transformed['messageText'] == 'This is a test email message.'

    def test_transform_message_incomplete(self, gmail_client, sample_incomplete_message):
        """Test message transformation with missing optional fields."""
        transformed = gmail_client._transform_message(sample_incomplete_message)
        
        assert isinstance(transformed, dict)
        assert transformed['messageId'] == 'msg789'
        assert transformed['threadId'] == 'thread012'
        # Check that timestamp is valid ISO format (timezone may vary)
        assert transformed['messageTimestamp'].startswith('2023-11-')
        assert 'T' in transformed['messageTimestamp']
        assert transformed['labelIds'] == []  # Default empty list
        assert transformed['sender'] == 'another@example.com'
        assert transformed['subject'] == ''  # Missing subject defaults to empty string
        assert transformed['messageText'] == 'Hello world!'

    @pytest.mark.asyncio
    @patch('gmail_client.build')
    async def test_get_profile_success(self, mock_build, gmail_client):
        """Test successful profile fetching."""
        sample_profile = {
            'emailAddress': 'user@example.com',
            'messagesTotal': 1500,
            'threadsTotal': 750,
            'historyId': 'hist123456'
        }
        
        # Mock the service and its methods
        mock_service = Mock()
        mock_users = Mock()
        mock_profile_method = Mock()
        
        mock_build.return_value = mock_service
        mock_service.users.return_value = mock_users
        mock_users.getProfile.return_value = mock_profile_method
        mock_profile_method.execute.return_value = sample_profile
        
        result = await gmail_client.get_profile()
        
        assert isinstance(result, dict)
        assert result['emailAddress'] == 'user@example.com'
        assert result['messagesTotal'] == 1500
        assert result['threadsTotal'] == 750
        assert result['historyId'] == 'hist123456'

    @pytest.mark.asyncio
    @patch('gmail_client.build')
    async def test_get_profile_api_error(self, mock_build, gmail_client):
        """Test profile fetching with API error."""
        from googleapiclient.errors import HttpError
        
        mock_service = Mock()
        mock_users = Mock()
        mock_profile_method = Mock()
        
        mock_build.return_value = mock_service
        mock_service.users.return_value = mock_users
        mock_users.getProfile.return_value = mock_profile_method
        mock_profile_method.execute.side_effect = HttpError(
            resp=Mock(status=403), content=b'Forbidden'
        )
        
        with pytest.raises(GmailAPIError, match="Failed to fetch profile"):
            await gmail_client.get_profile()

    @pytest.mark.asyncio
    @patch('gmail_client.build')
    async def test_get_labels_success(self, mock_build, gmail_client):
        """Test successful labels fetching."""
        sample_labels = {
            'labels': [
                {
                    'id': 'INBOX',
                    'name': 'INBOX',
                    'type': 'system',
                },
                {
                    'id': 'Label_1',
                    'name': 'Work',
                    'type': 'user'
                }
            ]
        }
        
        mock_service = Mock()
        mock_users = Mock()
        mock_labels = Mock()
        mock_list_method = Mock()
        
        mock_build.return_value = mock_service
        mock_service.users.return_value = mock_users
        mock_users.labels.return_value = mock_labels
        mock_labels.list.return_value = mock_list_method
        mock_list_method.execute.return_value = sample_labels
        
        result = await gmail_client.get_labels()
        
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]['id'] == 'INBOX'
        assert result[0]['name'] == 'INBOX'
        assert result[0]['type'] == 'system'
        assert result[1]['id'] == 'Label_1'
        assert result[1]['name'] == 'Work'
        assert result[1]['type'] == 'user'

    @pytest.mark.asyncio
    @patch('gmail_client.build')
    async def test_get_recent_emails_success(self, mock_build, gmail_client, sample_complete_message):
        """Test successful email fetching."""
        mock_service = Mock()
        mock_users = Mock()
        mock_messages = Mock()
        mock_list_method = Mock()
        mock_get_method = Mock()
        
        mock_build.return_value = mock_service
        mock_service.users.return_value = mock_users
        mock_users.messages.return_value = mock_messages
        mock_messages.list.return_value = mock_list_method
        mock_messages.get.return_value = mock_get_method
        
        # Mock the list response
        mock_list_method.execute.return_value = {
            'messages': [{'id': 'msg123'}]
        }
        
        # Mock the get response
        mock_get_method.execute.return_value = sample_complete_message
        
        result = await gmail_client.get_recent_emails(max_results=1)
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]['messageId'] == 'msg123'
        assert result[0]['sender'] == 'sender@example.com'

    @pytest.mark.asyncio
    @patch('gmail_client.build')
    async def test_get_recent_emails_empty(self, mock_build, gmail_client):
        """Test email fetching with no messages."""
        mock_service = Mock()
        mock_users = Mock()
        mock_messages = Mock()
        mock_list_method = Mock()
        
        mock_build.return_value = mock_service
        mock_service.users.return_value = mock_users
        mock_users.messages.return_value = mock_messages
        mock_messages.list.return_value = mock_list_method
        mock_list_method.execute.return_value = {'messages': []}
        
        result = await gmail_client.get_recent_emails()
        
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    @patch('gmail_client.build')
    async def test_fetch_all_data_success(self, mock_build, gmail_client, sample_complete_message):
        """Test successful fetching of all data concurrently."""
        sample_profile = {
            'emailAddress': 'user@example.com',
            'messagesTotal': 1500,
            'threadsTotal': 750,
            'historyId': 'hist123456'
        }
        
        sample_labels = {
            'labels': [
                {
                    'id': 'INBOX',
                    'name': 'INBOX',
                    'type': 'system',
                },
                {
                    'id': 'Label_1',
                    'name': 'Work',
                    'type': 'user'
                }
            ]
        }
        
        mock_service = Mock()
        mock_users = Mock()
        mock_profile_method = Mock()
        mock_labels = Mock()
        mock_list_labels_method = Mock()
        mock_messages = Mock()
        mock_list_messages_method = Mock()
        mock_get_method = Mock()
        
        mock_build.return_value = mock_service
        mock_service.users.return_value = mock_users
        
        # Profile mocks
        mock_users.getProfile.return_value = mock_profile_method
        mock_profile_method.execute.return_value = sample_profile
        
        # Labels mocks
        mock_users.labels.return_value = mock_labels
        mock_labels.list.return_value = mock_list_labels_method
        mock_list_labels_method.execute.return_value = sample_labels
        
        # Messages mocks
        mock_users.messages.return_value = mock_messages
        mock_messages.list.return_value = mock_list_messages_method
        mock_messages.get.return_value = mock_get_method
        mock_list_messages_method.execute.return_value = {
            'messages': [{'id': 'msg123'}]
        }
        mock_get_method.execute.return_value = sample_complete_message
        
        result = await gmail_client.fetch_all_data(max_emails=1)
        
        assert isinstance(result, dict)
        assert 'profile' in result
        assert 'labels' in result
        assert 'emails' in result
        
        assert result['profile']['emailAddress'] == 'user@example.com'
        assert len(result['labels']) == 2
        assert len(result['emails']) == 1
        assert result['emails'][0]['messageId'] == 'msg123'

    @pytest.mark.asyncio
    async def test_fetch_gmail_data_convenience_function(self, mock_credentials):
        """Test the convenience function for fetching Gmail data."""
        with patch.object(AsyncGmailClient, 'fetch_all_data') as mock_fetch:
            mock_fetch.return_value = {'test': 'data'}
            
            result = await fetch_gmail_data(mock_credentials, max_emails=5)
            
            assert result == {'test': 'data'}
            mock_fetch.assert_called_once_with(5)

    def test_gmail_api_error_inheritance(self):
        """Test that GmailAPIError is properly defined."""
        error = GmailAPIError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def gmail_client(self):
        """Create Gmail client for edge case testing."""
        mock_credentials = Mock()
        mock_credentials.expired = False
        mock_credentials.refresh_token = None
        return AsyncGmailClient(mock_credentials)

    def test_malformed_message_handling(self, gmail_client):
        """Test handling of malformed message data."""
        malformed_message = {
            'id': 'malformed123',
            # Missing threadId, internalDate, payload
        }
        
        transformed = gmail_client._transform_message(malformed_message)
        
        assert transformed['messageId'] == 'malformed123'
        assert transformed['threadId'] == ''
        assert transformed['labelIds'] == []
        assert transformed['sender'] == ''
        assert transformed['subject'] == ''
        assert transformed['messageText'] == ''

    def test_malformed_timestamp_handling(self, gmail_client):
        """Test handling of malformed timestamp."""
        message_with_bad_timestamp = {
            'id': 'msg123',
            'threadId': 'thread456',
            'internalDate': 'invalid_timestamp',
            'payload': {'headers': []}
        }
        
        transformed = gmail_client._transform_message(message_with_bad_timestamp)
        
        # Should default to epoch time when timestamp is invalid (timezone may vary)
        assert transformed['messageTimestamp'].startswith('1970-01-01T')
        assert 'T' in transformed['messageTimestamp']

    def test_nested_multipart_content_extraction(self, gmail_client):
        """Test extraction from deeply nested multipart messages."""
        complex_payload = {
            'mimeType': 'multipart/mixed',
            'parts': [
                {
                    'mimeType': 'multipart/alternative',
                    'parts': [
                        {
                            'mimeType': 'text/plain',
                            'body': {
                                'data': 'TmVzdGVkIGNvbnRlbnQ='  # base64: "Nested content"
                            }
                        }
                    ]
                }
            ]
        }
        
        content = gmail_client._extract_email_content(complex_payload)
        assert content == 'Nested content'


if __name__ == '__main__':
    pytest.main([__file__]) 