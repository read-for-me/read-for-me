"""
Crawlers Package

확장 가능한 웹 크롤러 모듈입니다.
다양한 웹 소스(GeekNews, GitHub, Substack 등)를 크롤링할 수 있습니다.

Usage:
    from crawlers import GeekNewsWeeklyCrawler, GeekNewsArticleCrawler
    
    # Weekly 크롤링
    with GeekNewsWeeklyCrawler() as crawler:
        crawler.crawl_and_save("https://news.hada.io/weekly/202546")
    
    # Article 크롤링
    with GeekNewsArticleCrawler(include_comments=True) as crawler:
        crawler.crawl_and_save("https://news.hada.io/topic?id=24268")
"""

from .base_crawler import BaseCrawler, CrawledContent, BaseTextExtractor
from .geeknews_base import GeekNewsBaseCrawler, GeekNewsTextExtractor
from .geeknews_weekly_crawler import GeekNewsWeeklyCrawler
from .geeknews_article_crawler import GeekNewsArticleCrawler

__all__ = [
    # Base classes
    "BaseCrawler",
    "CrawledContent",
    "BaseTextExtractor",
    
    # GeekNews crawlers
    "GeekNewsBaseCrawler",
    "GeekNewsTextExtractor",
    "GeekNewsWeeklyCrawler",
    "GeekNewsArticleCrawler",
]

__version__ = "1.0.0"