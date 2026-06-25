// Paste in browser console on X.com
function collectTweets() {
    const tweets = [];
    document.querySelectorAll('article[data-testid="tweet"]').forEach(tweet => {
        const link = tweet.querySelector('a[href*="/status/"]');
        if (!link) return;
        const id = link.href.match(/status\/(\d+)/)?.[1];
        const text = tweet.querySelector('[data-testid="tweetText"]')?.innerText || '';
        const author = tweet.querySelector('a[role="link"] span')?.innerText || '';
        
        if (id) tweets.push({
            id: id,
            author: author,
            text: text.substring(0, 280),
            type: text.toLowerCase().includes('physics') ? 'physics' : 'general'
        });
    });
    
    const json = JSON.stringify({tweets: tweets}, null, 2);
    navigator.clipboard.writeText(json);
    console.log('Copied ' + tweets.length + ' tweets to clipboard');
}
collectTweets();