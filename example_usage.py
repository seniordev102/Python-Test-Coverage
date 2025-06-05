"""
Example usage of the Gmail API client.

This script demonstrates how to use the AsyncGmailClient to fetch
user profile, labels, and recent emails efficiently.
"""

import asyncio
import os
from typing import Dict, Any

from google.oauth2.credentials import Credentials
from gmail_client import fetch_gmail_data, AsyncGmailClient, GmailAPIError


def create_credentials_from_env() -> Credentials:
    """
    Create credentials from environment variables.
    
    Set these environment variables:
    - GMAIL_ACCESS_TOKEN
    - GMAIL_REFRESH_TOKEN
    - GMAIL_CLIENT_ID
    - GMAIL_CLIENT_SECRET
    """
    return Credentials(
        token=os.getenv('GMAIL_ACCESS_TOKEN'),
        refresh_token=os.getenv('GMAIL_REFRESH_TOKEN'),
        token_uri='https://oauth2.googleapis.com/token',
        client_id=os.getenv('GMAIL_CLIENT_ID'),
        client_secret=os.getenv('GMAIL_CLIENT_SECRET'),
        scopes=['https://www.googleapis.com/auth/gmail.readonly']
    )


async def main():
    """Main example function demonstrating Gmail API client usage."""
    try:
        # Initialize credentials
        credentials = create_credentials_from_env()
        
        print("🚀 Fetching Gmail data asynchronously...")
        
        # Method 1: Fetch all data concurrently (recommended for speed)
        print("\n📊 Method 1: Concurrent fetch of all data")
        data = await fetch_gmail_data(credentials, max_emails=5)
        
        # Display profile information
        profile = data['profile']
        print(f"\n👤 Profile Information:")
        print(f"   Email: {profile['emailAddress']}")
        print(f"   Total Messages: {profile['messagesTotal']:,}")
        print(f"   Total Threads: {profile['threadsTotal']:,}")
        print(f"   History ID: {profile['historyId']}")
        
        # Display labels
        labels = data['labels']
        print(f"\n🏷️  Labels ({len(labels)} total):")
        system_labels = [l for l in labels if l['type'] == 'system']
        user_labels = [l for l in labels if l['type'] == 'user']
        
        print(f"   System labels: {len(system_labels)}")
        for label in system_labels[:5]:  # Show first 5 system labels
            print(f"     - {label['name']} (ID: {label['id']})")
        
        print(f"   User labels: {len(user_labels)}")
        for label in user_labels[:5]:  # Show first 5 user labels
            print(f"     - {label['name']} (ID: {label['id']})")
        
        # Display recent emails
        emails = data['emails']
        print(f"\n📧 Recent Emails ({len(emails)} fetched):")
        for i, email in enumerate(emails, 1):
            # Truncate long subjects and text
            subject = email['subject'][:50] + "..." if len(email['subject']) > 50 else email['subject']
            text_preview = email['messageText'][:100] + "..." if len(email['messageText']) > 100 else email['messageText']
            text_preview = text_preview.replace('\n', ' ')  # Remove newlines for clean display
            
            print(f"\n   📨 Email {i}:")
            print(f"      From: {email['sender']}")
            print(f"      Subject: {subject}")
            print(f"      Timestamp: {email['messageTimestamp']}")
            print(f"      Labels: {', '.join(email['labelIds'][:3])}{'...' if len(email['labelIds']) > 3 else ''}")
            print(f"      Preview: {text_preview}")
        
        print("\n" + "="*60)
        
        # Method 2: Individual method calls (for more control)
        print("\n📊 Method 2: Individual method calls")
        client = AsyncGmailClient(credentials)
        
        # Fetch components individually
        print("   Fetching profile...")
        profile = await client.get_profile()
        print(f"   ✅ Profile fetched for {profile['emailAddress']}")
        
        print("   Fetching labels...")
        labels = await client.get_labels()
        print(f"   ✅ {len(labels)} labels fetched")
        
        print("   Fetching recent emails...")
        emails = await client.get_recent_emails(max_results=3)
        print(f"   ✅ {len(emails)} emails fetched")
        
        # Analyze email patterns
        print(f"\n📈 Email Analysis:")
        if emails:
            senders = {}
            for email in emails:
                sender = email['sender']
                senders[sender] = senders.get(sender, 0) + 1
            
            print(f"   Most frequent senders:")
            for sender, count in sorted(senders.items(), key=lambda x: x[1], reverse=True)[:3]:
                print(f"     - {sender}: {count} email(s)")
        
        print(f"\n✨ Successfully processed {len(emails)} emails with essential fields only!")
        print(f"   Data transformation reduced verbose API responses to {len(data['emails'][0].keys()) if emails else 0} essential fields")
        
    except GmailAPIError as e:
        print(f"❌ Gmail API Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


async def performance_demo():
    """Demonstrate the performance benefits of async fetching."""
    import time
    
    try:
        credentials = create_credentials_from_env()
        client = AsyncGmailClient(credentials)
        
        print("\n⚡ Performance Demonstration")
        print("Comparing sequential vs concurrent data fetching...\n")
        
        # Sequential fetching
        print("🐌 Sequential fetching:")
        start_time = time.time()
        
        profile = await client.get_profile()
        print(f"   Profile fetched in {time.time() - start_time:.2f}s")
        
        labels_start = time.time()
        labels = await client.get_labels()
        print(f"   Labels fetched in {time.time() - labels_start:.2f}s")
        
        emails_start = time.time()
        emails = await client.get_recent_emails(max_results=5)
        sequential_total = time.time() - start_time
        print(f"   Emails fetched in {time.time() - emails_start:.2f}s")
        print(f"   Total sequential time: {sequential_total:.2f}s")
        
        # Concurrent fetching
        print(f"\n🚀 Concurrent fetching:")
        start_time = time.time()
        data = await client.fetch_all_data(max_emails=5)
        concurrent_total = time.time() - start_time
        print(f"   All data fetched concurrently in {concurrent_total:.2f}s")
        
        # Performance improvement
        improvement = ((sequential_total - concurrent_total) / sequential_total) * 100
        print(f"   ⚡ Performance improvement: {improvement:.1f}% faster!")
        
    except Exception as e:
        print(f"❌ Performance demo error: {e}")


if __name__ == "__main__":
    print("Gmail API Client Example")
    print("=" * 50)
    
    # Check if environment variables are set
    required_env_vars = ['GMAIL_ACCESS_TOKEN', 'GMAIL_REFRESH_TOKEN', 'GMAIL_CLIENT_ID', 'GMAIL_CLIENT_SECRET']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these environment variables before running the example.")
        print("See README.md for instructions on obtaining Gmail API credentials.")
    else:
        # Run the main example
        asyncio.run(main())
        
        # Optionally run performance demo
        print("\n" + "="*60)
        response = input("\nRun performance demonstration? (y/N): ")
        if response.lower() == 'y':
            asyncio.run(performance_demo()) 