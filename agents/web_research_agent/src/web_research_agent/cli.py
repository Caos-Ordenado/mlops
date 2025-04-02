"""
CLI interface for the web research agent.
"""

import asyncio
import argparse
from typing import List
import sys
import json
from .agent import WebResearchAgent, ResearchRequest, ResearchResponse

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Web Research Agent - Crawl websites and analyze content using LLM"
    )
    
    parser.add_argument(
        "urls",
        nargs="+",
        help="One or more URLs to research"
    )
    
    parser.add_argument(
        "--query", "-q",
        required=True,
        help="Research query to answer based on the crawled content"
    )
    
    parser.add_argument(
        "--max-pages", "-p",
        type=int,
        default=5,
        help="Maximum number of pages to crawl (default: 5)"
    )
    
    parser.add_argument(
        "--max-depth", "-d",
        type=int,
        default=2,
        help="Maximum crawl depth (default: 2)"
    )
    
    parser.add_argument(
        "--model", "-m",
        default="llama2",
        help="Ollama model to use (default: llama2)"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format"
    )
    
    return parser.parse_args()

async def main():
    """Main CLI entry point."""
    args = parse_args()
    
    # Create research request
    request = ResearchRequest(
        urls=args.urls,
        query=args.query,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        model=args.model
    )
    
    try:
        async with WebResearchAgent() as agent:
            # Show progress
            if not args.json:
                print("Initializing research agent...", file=sys.stderr)
                print(f"Researching {len(args.urls)} URLs...", file=sys.stderr)
            
            # Perform research
            response = await agent.research(request)
            
            # Output results
            if args.json:
                # JSON output
                print(json.dumps({
                    "summary": response.summary,
                    "sources": response.sources
                }, indent=2))
            else:
                # Human-readable output
                print("\nResearch Results:")
                print("-" * 50)
                print("\nSummary:")
                print(response.summary)
                print("\nSources:")
                for source in response.sources:
                    print(f"- {source['title']}: {source['url']}")
                    
    except Exception as e:
        if args.json:
            print(json.dumps({
                "error": str(e)
            }, indent=2))
        else:
            print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 