"""
Gmail API Client for fetching and transforming email data.

This module provides an async Gmail client that efficiently fetches user labels,
profile information, and recent emails with proper data transformation.
"""

import asyncio
import base64
from datetime import datetime
from typing import Dict, List, Optional, TypedDict, Union
import concurrent.futures

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Define the fields we want to extract from Gmail messages
GMAIL_FIELDS = [
    "messageId",
    "threadId", 
    "messageTimestamp",
    "labelIds",
    "sender",
    "subject",
    "messageText",
]


class GmailMessage(TypedDict):
    """Type definition for transformed Gmail message."""
    messageId: str
    threadId: str
    messageTimestamp: str
    labelIds: List[str]
    sender: str
    subject: str
    messageText: str


class GmailProfile(TypedDict):
    """Type definition for Gmail user profile."""
    emailAddress: str
    messagesTotal: int
    threadsTotal: int
    historyId: str


class GmailLabel(TypedDict):
    """Type definition for Gmail label."""
    id: str
    name: str
    type: str


class GmailAPIError(Exception):
    """Custom exception for Gmail API errors."""
    pass


class AsyncGmailClient:
    """
    Async Gmail API client for efficient data fetching and transformation.
    
    This client fetches user profile, labels, and recent emails concurrently
    for optimal performance, while transforming the verbose Gmail API responses
    into clean, essential data structures suitable for AI agent processing.
    """

    def __init__(self, credentials: Credentials) -> None:
        """
        Initialize the Gmail client with OAuth2 credentials.
        
        Args:
            credentials: Google OAuth2 credentials object
        """
        self.credentials = credentials
        self.service = None

    def _get_service(self):
        """Get or create the Gmail service instance."""
        if self.service is None:
            # Refresh credentials if needed
            if self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
            
            self.service = build('gmail', 'v1', credentials=self.credentials)
        return self.service

    def _extract_email_content(self, payload: Dict) -> str:
        """
        Extract text content from email payload.
        
        Args:
            payload: Gmail message payload
            
        Returns:
            Decoded email text content
        """
        def _get_text_from_part(part: Dict) -> str:
            """Recursively extract text from message parts."""
            if part.get('mimeType') == 'text/plain':
                data = part.get('body', {}).get('data', '')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            
            elif part.get('mimeType') == 'text/html':
                # Fallback to HTML if no plain text
                data = part.get('body', {}).get('data', '')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            
            # Check nested parts
            for subpart in part.get('parts', []):
                text = _get_text_from_part(subpart)
                if text:
                    return text
            
            return ""

        # Handle single part message
        if payload.get('mimeType') == 'text/plain':
            data = payload.get('body', {}).get('data', '')
            if data:
                return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        
        # Handle multipart message
        return _get_text_from_part(payload)

    def _extract_header_value(self, headers: List[Dict], name: str) -> str:
        """
        Extract specific header value from email headers.
        
        Args:
            headers: List of email headers
            name: Header name to extract
            
        Returns:
            Header value or empty string if not found
        """
        for header in headers:
            if header.get('name', '').lower() == name.lower():
                return header.get('value', '')
        return ''

    def _transform_message(self, message: Dict) -> GmailMessage:
        """
        Transform verbose Gmail message into clean format with essential fields.
        
        Args:
            message: Raw Gmail API message response
            
        Returns:
            Transformed message with only essential fields
        """
        payload = message.get('payload', {})
        headers = payload.get('headers', [])
        
        # Extract timestamp and convert to ISO format
        try:
            timestamp_ms = int(message.get('internalDate', '0'))
            timestamp = datetime.fromtimestamp(timestamp_ms / 1000).isoformat()
        except (ValueError, TypeError):
            # Handle malformed timestamp by defaulting to epoch
            timestamp = datetime.fromtimestamp(0).isoformat()
        
        return GmailMessage(
            messageId=message.get('id', ''),
            threadId=message.get('threadId', ''),
            messageTimestamp=timestamp,
            labelIds=message.get('labelIds', []),
            sender=self._extract_header_value(headers, 'From'),
            subject=self._extract_header_value(headers, 'Subject'),
            messageText=self._extract_email_content(payload)
        )

    async def get_profile(self) -> GmailProfile:
        """
        Fetch user's Gmail profile information.
        
        Returns:
            User profile with email address and message counts
            
        Raises:
            GmailAPIError: If API request fails
        """
        try:
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                service = self._get_service()
                profile = await loop.run_in_executor(
                    executor, 
                    lambda: service.users().getProfile(userId='me').execute()
                )
            
            return GmailProfile(
                emailAddress=profile.get('emailAddress', ''),
                messagesTotal=profile.get('messagesTotal', 0),
                threadsTotal=profile.get('threadsTotal', 0),
                historyId=profile.get('historyId', '')
            )
        except HttpError as e:
            raise GmailAPIError(f"Failed to fetch profile: {e}")

    async def get_labels(self) -> List[GmailLabel]:
        """
        Fetch user's Gmail labels.
        
        Returns:
            List of Gmail labels
            
        Raises:
            GmailAPIError: If API request fails
        """
        try:
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                service = self._get_service()
                labels_result = await loop.run_in_executor(
                    executor,
                    lambda: service.users().labels().list(userId='me').execute()
                )
            
            labels = labels_result.get('labels', [])
            return [
                GmailLabel(
                    id=label.get('id', ''),
                    name=label.get('name', ''),
                    type=label.get('type', ''),
                    messageListVisibility=label.get('messageListVisibility', ''),
                    labelListVisibility=label.get('labelListVisibility', '')
                )
                for label in labels
            ]
        except HttpError as e:
            raise GmailAPIError(f"Failed to fetch labels: {e}")

    async def get_recent_emails(self, max_results: int = 10) -> List[GmailMessage]:
        """
        Fetch user's most recent emails with full message content.
        
        Args:
            max_results: Maximum number of emails to fetch (default: 10)
            
        Returns:
            List of transformed email messages with essential fields only
            
        Raises:
            GmailAPIError: If API request fails
        """
        try:
            loop = asyncio.get_event_loop()
            service = self._get_service()
            
            # First, get list of message IDs
            with concurrent.futures.ThreadPoolExecutor() as executor:
                messages_result = await loop.run_in_executor(
                    executor,
                    lambda: service.users().messages().list(
                        userId='me', maxResults=max_results
                    ).execute()
                )
            
            message_ids = [msg['id'] for msg in messages_result.get('messages', [])]
            
            if not message_ids:
                return []
            
            # Fetch full message details concurrently
            async def fetch_message(msg_id: str) -> Dict:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    return await loop.run_in_executor(
                        executor,
                        lambda: service.users().messages().get(
                            userId='me', id=msg_id, format='full'
                        ).execute()
                    )
            
            tasks = [fetch_message(msg_id) for msg_id in message_ids]
            messages = await asyncio.gather(*tasks)
            
            # Transform messages to include only essential fields
            return [self._transform_message(msg) for msg in messages]
            
        except HttpError as e:
            raise GmailAPIError(f"Failed to fetch emails: {e}")

    async def fetch_all_data(self, max_emails: int = 10) -> Dict[str, Union[GmailProfile, List[GmailLabel], List[GmailMessage]]]:
        """
        Fetch user profile, labels, and recent emails concurrently for optimal performance.
        
        Args:
            max_emails: Maximum number of recent emails to fetch
            
        Returns:
            Dictionary containing profile, labels, and emails data
            
        Raises:
            GmailAPIError: If any API request fails
        """
        try:
            # Execute all requests concurrently for maximum speed
            profile, labels, emails = await asyncio.gather(
                self.get_profile(),
                self.get_labels(),
                self.get_recent_emails(max_emails)
            )
            
            return {
                'profile': profile,
                'labels': labels,
                'emails': emails
            }
            
        except Exception as e:
            raise GmailAPIError(f"Failed to fetch Gmail data: {e}")


# Convenience function for easy usage
async def fetch_gmail_data(credentials: Credentials, max_emails: int = 10) -> Dict[str, Union[GmailProfile, List[GmailLabel], List[GmailMessage]]]:
    """
    Convenience function to fetch all Gmail data in one call.
    
    Args:
        credentials: Google OAuth2 credentials
        max_emails: Maximum number of recent emails to fetch
        
    Returns:
        Dictionary containing profile, labels, and emails data
    """
    client = AsyncGmailClient(credentials)
    return await client.fetch_all_data(max_emails) 