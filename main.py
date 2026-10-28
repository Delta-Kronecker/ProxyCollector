#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Proxy Collector - Entry point
"""

if __name__ == "__main__":
    import asyncio
    from src.collector import main
    asyncio.run(main())