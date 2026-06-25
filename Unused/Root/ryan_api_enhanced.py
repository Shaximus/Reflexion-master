#!/usr/bin/env python3
"""
ENHANCED Ryan API - Extracts ALL available data from tweets
"""

import os
import json
import requests
import logging
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("ryan_api_enhanced")

class RyanTwitterAPIEnhanced:
    """Enhanced API that extracts ALL data from tweets"""

    def __init__(self):
        self.api_key = os.getenv("RAPIDAPI_KEY")
        if not self.api_key:
            raise ValueError("RAPIDAPI_KEY not found in environment")

        self.headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": "twitter-api47.p.rapidapi.com",
            "Content-Type": "application/json",
        }
        self.base_url = "https://twitter-api47.p.rapidapi.com"

    def extract_full_tweet_data(self, raw_tweet: Dict) -> Dict:
        """Extract ALL available data from a raw tweet response"""

        # Navigate to the actual tweet data
        content = raw_tweet.get('content', {})
        item_content = content.get('itemContent', {})
        tweet_results = item_content.get('tweet_results', {})
        result = tweet_results.get('result', {})

        # Get legacy tweet data
        legacy = result.get('legacy', {})

        # Get user data
        core = result.get('core', {})
        user_results = core.get('user_results', {})
        user_result = user_results.get('result', {})
        user_legacy = user_result.get('legacy', {})

        # Extract entities
        entities = legacy.get('entities', {})

        # Build comprehensive tweet object
        return {
            # Tweet IDs
            'tweet_id': result.get('rest_id'),
            'conversation_id': legacy.get('conversation_id_str'),
            'in_reply_to_status_id': legacy.get('in_reply_to_status_id_str'),
            'in_reply_to_user_id': legacy.get('in_reply_to_user_id_str'),

            # Tweet content
            'text': legacy.get('full_text', ''),
            'created_at': legacy.get('created_at'),
            'lang': legacy.get('lang'),
            'source': legacy.get('source'),

            # Metrics
            'metrics': {
                'retweet_count': legacy.get('retweet_count', 0),
                'favorite_count': legacy.get('favorite_count', 0),
                'reply_count': legacy.get('reply_count', 0),
                'quote_count': legacy.get('quote_count', 0),
                'bookmark_count': legacy.get('bookmark_count', 0),
                'impression_count': int(result.get('views', {}).get('count', 0) or 0)
            },

            # Entities
            'entities': {
                'hashtags': [h.get('text', '') for h in entities.get('hashtags', [])],
                'urls': [{
                    'url': u.get('url'),
                    'expanded_url': u.get('expanded_url'),
                    'display_url': u.get('display_url')
                } for u in entities.get('urls', [])],
                'user_mentions': [{
                    'screen_name': m.get('screen_name'),
                    'name': m.get('name'),
                    'id': m.get('id_str')
                } for m in entities.get('user_mentions', [])],
                'media': [{
                    'type': m.get('type'),
                    'url': m.get('media_url_https')
                } for m in entities.get('media', [])]
            },

            # User/Author data
            'author': {
                'user_id': user_result.get('rest_id'),
                'username': user_legacy.get('screen_name'),
                'name': user_legacy.get('name'),
                'description': user_legacy.get('description'),
                'location': user_legacy.get('location'),
                'created_at': user_legacy.get('created_at'),
                'verified': user_result.get('is_blue_verified', False),
                'verified_legacy': user_legacy.get('verified', False),
                'protected': user_legacy.get('protected', False),
                'followers_count': user_legacy.get('followers_count', 0),
                'following_count': user_legacy.get('friends_count', 0),
                'tweet_count': user_legacy.get('statuses_count', 0),
                'listed_count': user_legacy.get('listed_count', 0),
                'favourites_count': user_legacy.get('favourites_count', 0),
                'media_count': user_legacy.get('media_count', 0),
                'profile_image_url': user_legacy.get('profile_image_url_https'),
                'profile_banner_url': user_legacy.get('profile_banner_url'),
                'default_profile': user_legacy.get('default_profile', False),
                'default_profile_image': user_legacy.get('default_profile_image', False),
                'has_custom_timelines': user_legacy.get('has_custom_timelines', False),
                'possibly_sensitive': user_legacy.get('possibly_sensitive', False),
                'withheld_in_countries': user_legacy.get('withheld_in_countries', [])
            },

            # Flags
            'is_quote_status': legacy.get('is_quote_status', False),
            'possibly_sensitive': legacy.get('possibly_sensitive', False),
            'retweeted': legacy.get('retweeted', False),
            'favorited': legacy.get('favorited', False)
        }

    def search_tweets_enhanced(self, query: str, limit: int = 20) -> List[Dict]:
        """Search tweets and return ALL available data"""

        url = f"{self.base_url}/v2/search"
        params = {
            "query": query,
            "limit": limit,
            "type": "Latest"
        }

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                tweets = data.get('tweets', [])

                # Extract full data from each tweet
                enhanced_tweets = []
                for tweet in tweets:
                    try:
                        enhanced_tweet = self.extract_full_tweet_data(tweet)
                        enhanced_tweets.append(enhanced_tweet)
                    except Exception as e:
                        logger.error(f"Error extracting tweet data: {e}")
                        continue

                return enhanced_tweets
            else:
                logger.error(f"API returned {response.status_code}: {response.text}")
                return []

        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

    def get_user_tweets_enhanced(self, username: str, limit: int = 20) -> List[Dict]:
        """Get user tweets with ALL data"""
        return self.search_tweets_enhanced(f"from:{username}", limit)

    def analyze_for_bot_detection(self, tweets: List[Dict]) -> Dict:
        """Analyze tweets for bot detection features"""

        if not tweets:
            return {}

        # Aggregate metrics
        total_tweets = len(tweets)
        total_retweets = sum(t['metrics']['retweet_count'] for t in tweets)
        total_likes = sum(t['metrics']['favorite_count'] for t in tweets)
        total_replies = sum(t['metrics']['reply_count'] for t in tweets)
        total_impressions = sum(t['metrics']['impression_count'] for t in tweets)

        # User metrics (from first tweet's author data)
        author = tweets[0]['author'] if tweets else {}

        # Entity analysis
        total_hashtags = sum(len(t['entities']['hashtags']) for t in tweets)
        total_urls = sum(len(t['entities']['urls']) for t in tweets)
        total_mentions = sum(len(t['entities']['user_mentions']) for t in tweets)
        total_media = sum(len(t['entities']['media']) for t in tweets)

        # Text analysis
        texts = [t['text'] for t in tweets]
        unique_texts = len(set(texts))
        duplicate_ratio = 1 - (unique_texts / total_tweets) if total_tweets > 0 else 0

        # Time analysis
        tweet_times = [t['created_at'] for t in tweets if t['created_at']]

        return {
            'user_features': {
                'username': author.get('username'),
                'user_id': author.get('user_id'),
                'account_age_days': self._calculate_account_age(author.get('created_at')),
                'followers': author.get('followers_count', 0),
                'following': author.get('following_count', 0),
                'ff_ratio': author.get('following_count', 0) / max(author.get('followers_count', 1), 1),
                'total_tweets': author.get('tweet_count', 0),
                'listed_count': author.get('listed_count', 0),
                'verified': author.get('verified', False),
                'default_profile': author.get('default_profile', False),
                'default_profile_image': author.get('default_profile_image', False),
                'has_description': bool(author.get('description')),
                'has_location': bool(author.get('location')),
                'profile_has_banner': bool(author.get('profile_banner_url'))
            },
            'tweet_features': {
                'total_tweets_analyzed': total_tweets,
                'avg_retweets': total_retweets / total_tweets if total_tweets > 0 else 0,
                'avg_likes': total_likes / total_tweets if total_tweets > 0 else 0,
                'avg_replies': total_replies / total_tweets if total_tweets > 0 else 0,
                'avg_impressions': total_impressions / total_tweets if total_tweets > 0 else 0,
                'engagement_rate': (total_likes + total_retweets) / max(total_impressions, 1),
                'duplicate_text_ratio': duplicate_ratio,
                'hashtags_per_tweet': total_hashtags / total_tweets if total_tweets > 0 else 0,
                'urls_per_tweet': total_urls / total_tweets if total_tweets > 0 else 0,
                'mentions_per_tweet': total_mentions / total_tweets if total_tweets > 0 else 0,
                'media_per_tweet': total_media / total_tweets if total_tweets > 0 else 0,
            },
            'bot_likelihood_factors': {
                'high_ff_ratio': author.get('following_count', 0) / max(author.get('followers_count', 1), 1) > 10,
                'low_engagement': (total_likes + total_retweets) / max(total_impressions, 1) < 0.01,
                'high_duplicate_ratio': duplicate_ratio > 0.5,
                'default_profile': author.get('default_profile', False),
                'no_profile_customization': author.get('default_profile_image', False),
                'suspicious_username': self._check_suspicious_username(author.get('username', ''))
            }
        }

    def _calculate_account_age(self, created_at: str) -> int:
        """Calculate account age in days"""
        if not created_at:
            return 0
        try:
            from datetime import datetime
            # Parse Twitter date format: "Tue Jun 02 20:12:29 +0000 2009"
            created = datetime.strptime(created_at, "%a %b %d %H:%M:%S +0000 %Y")
            age = (datetime.now() - created).days
            return age
        except:
            return 0

    def _check_suspicious_username(self, username: str) -> bool:
        """Check if username has bot-like patterns"""
        if not username:
            return False

        # Count digits
        digit_count = sum(c.isdigit() for c in username)
        digit_ratio = digit_count / len(username)

        # Check for patterns
        has_many_numbers = digit_ratio > 0.3
        has_many_underscores = username.count('_') > 2
        ends_with_numbers = username[-4:].isdigit() if len(username) > 4 else False

        return has_many_numbers or has_many_underscores or ends_with_numbers

# Test it
if __name__ == "__main__":
    api = RyanTwitterAPIEnhanced()

    # Test with a user
    print("Testing enhanced API with @elonmusk tweets...")
    tweets = api.get_user_tweets_enhanced("elonmusk", limit=5)

    if tweets:
        print(f"\nGot {len(tweets)} tweets with FULL data")

        # Show first tweet
        first = tweets[0]
        print(f"\nFirst tweet data:")
        print(f"  Text: {first['text'][:100]}...")
        print(f"  Metrics: {first['metrics']}")
        print(f"  Author followers: {first['author']['followers_count']:,}")
        print(f"  Author verified: {first['author']['verified']}")

        # Analyze for bot detection
        analysis = api.analyze_for_bot_detection(tweets)
        print(f"\nBot Detection Analysis:")
        print(f"  User features: {analysis['user_features']}")
        print(f"  Tweet features: {analysis['tweet_features']}")
        print(f"  Bot likelihood: {analysis['bot_likelihood_factors']}")
    else:
        print("No tweets returned")