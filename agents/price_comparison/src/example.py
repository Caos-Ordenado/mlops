import asyncio
from loguru import logger
from models.price_comparison_agent import PriceComparisonAgent

async def main():
    # Initialize the agent
    agent = PriceComparisonAgent()
    await agent.initialize()
    
    try:
        # Store some sample prices
        sample_products = [
            {
                "name": "Coca-Cola Original 2L Bottle",
                "store": "SupermarketA",
                "price": 2.49,
                "url": "http://supermarketa.com/coca-cola-2l"
            },
            {
                "name": "Coca Cola 2 Liter",
                "store": "SupermarketB",
                "price": 2.29,
                "url": "http://supermarketb.com/coke-2l"
            },
            {
                "name": "Diet Coke 2L",
                "store": "SupermarketA",
                "price": 2.39,
                "url": "http://supermarketa.com/diet-coke-2l"
            }
        ]
        
        # Store the prices
        for product in sample_products:
            await agent.store_product_price(
                raw_name=product["name"],
                store=product["store"],
                price=product["price"],
                url=product["url"]
            )
            logger.info(f"Stored price for {product['name']}")
        
        # Compare prices for a product
        comparison = await agent.compare_products("Coca-Cola Original 2L Bottle")
        logger.info("\nPrice Comparison Results:")
        logger.info(f"Product: {comparison.product_name}")
        logger.info(f"Normalized Name: {comparison.normalized_name}")
        logger.info(f"Best Price: ${comparison.best_price:.2f} at {comparison.best_price_store}")
        logger.info(f"Price Difference: ${comparison.price_difference:.2f} ({comparison.price_difference_percentage:.1f}%)")
        logger.info("All Prices:")
        for store, price in comparison.all_prices.items():
            logger.info(f"  {store}: ${price:.2f}")
        
        # Get historical trends
        trends = await agent.get_historical_trends("Coca-Cola Original 2L Bottle")
        logger.info("\nHistorical Trends:")
        logger.info(f"Average Price: ${trends['avg_price']:.2f}")
        logger.info(f"Price Range: ${trends['min_price']:.2f} - ${trends['max_price']:.2f}")
        logger.info(f"Number of Records: {trends['num_records']}")
        
    except Exception as e:
        logger.error(f"Error in example: {e}")
    finally:
        await agent.close()

if __name__ == "__main__":
    asyncio.run(main()) 