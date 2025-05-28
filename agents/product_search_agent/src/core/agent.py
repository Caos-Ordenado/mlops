from shared.logging import setup_logger
from src.api.models import BraveSearchResult, ExtractedUrlInfo, IdentifiedPageCandidate
from .query_generator import QueryGeneratorAgent
from .search_agent import SearchAgent
from .query_validator import QueryValidatorAgent
from .url_extractor_agent import UrlExtractorAgent
from .product_page_candidate_identifier import ProductPageCandidateIdentifierAgent
from .price_extractor import PriceExtractorAgent
import inspect

logger = setup_logger("product_search_agent")

MAX_VALIDATION_ATTEMPTS = 3
TARGET_VALID_QUERIES = 5

class ProductSearchAgent:
    def __init__(self):
        logger.info("ProductSearchAgent initialized")
        self.query_generator = QueryGeneratorAgent()
        self.search_agent = SearchAgent()
        self.query_validator = QueryValidatorAgent()
        
        self.url_extractor = UrlExtractorAgent()
        self.page_identifier = ProductPageCandidateIdentifierAgent()
        self.price_extractor = PriceExtractorAgent()

        if not hasattr(self.url_extractor, '__aenter__') or not callable(getattr(self.url_extractor, '__aenter__')):
            logger.error("CRITICAL: self.url_extractor INSTANCE does NOT have a callable __aenter__ attribute at init!")
        else:
            logger.info("SUCCESS: self.url_extractor INSTANCE HAS a callable __aenter__.")
        
        if not hasattr(self.url_extractor, '__aexit__') or not callable(getattr(self.url_extractor, '__aexit__')):
            logger.error("CRITICAL: self.url_extractor INSTANCE does NOT have a callable __aexit__ attribute at init!")
        else:
            logger.info("SUCCESS: self.url_extractor INSTANCE HAS a callable __aexit__.")

    async def __aenter__(self):
        logger.debug("Entering ProductSearchAgent context")
        await self.query_generator.__aenter__()
        await self.search_agent.__aenter__()
        await self.query_validator.__aenter__()
        if self.url_extractor and hasattr(self.url_extractor, '__aenter__') and callable(getattr(self.url_extractor, '__aenter__')):
            await self.url_extractor.__aenter__()
        else:
            logger.error("Skipping await self.url_extractor.__aenter__() because it is missing or not callable at __aenter__ call time.")
        await self.page_identifier.__aenter__()
        await self.price_extractor.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.debug("Exiting ProductSearchAgent context")
        await self.query_generator.__aexit__(exc_type, exc_val, exc_tb)
        await self.search_agent.__aexit__(exc_type, exc_val, exc_tb)
        await self.query_validator.__aexit__(exc_type, exc_val, exc_tb)
        if self.url_extractor and hasattr(self.url_extractor, '__aexit__') and callable(getattr(self.url_extractor, '__aexit__')):
            await self.url_extractor.__aexit__(exc_type, exc_val, exc_tb)
        else:
            logger.error("Skipping await self.url_extractor.__aexit__() because it is missing or not callable at __aexit__ call time.")
        await self.page_identifier.__aexit__(exc_type, exc_val, exc_tb)
        await self.price_extractor.__aexit__(exc_type, exc_val, exc_tb)

    async def search_product(self, product: str):
        logger.info(f"Original product search query: {product}")
        
        validation_attempts_count = 0
        valid_queries = [] 
        extracted_candidates_list = []
        identified_page_candidates_list = []

        for attempt in range(MAX_VALIDATION_ATTEMPTS):
            validation_attempts_count = attempt + 1
            logger.info(f"Query generation and validation attempt: {validation_attempts_count}")

            generated_queries, _ = await self.query_generator.generate_queries(product)
            if not generated_queries:
                logger.warning(f"Query generator returned no queries on attempt {validation_attempts_count}.")
                continue

            current_attempt_validation_details = await self.query_validator.validate_queries(generated_queries)
            current_valid_queries = [detail["query"] for detail in current_attempt_validation_details if detail.get("valid")]
            valid_queries.extend(current_valid_queries)
            valid_queries = list(dict.fromkeys(valid_queries))
            
            logger.info(f"Attempt {validation_attempts_count}: Found {len(current_valid_queries)} new valid queries. Total unique valid: {len(valid_queries)}.")

            if len(valid_queries) >= TARGET_VALID_QUERIES:
                logger.info(f"Reached target of {TARGET_VALID_QUERIES} valid queries.")
                valid_queries = valid_queries[:TARGET_VALID_QUERIES]
                break
        else:
            logger.warning(f"Failed to obtain {TARGET_VALID_QUERIES} valid queries after {MAX_VALIDATION_ATTEMPTS} attempts. Proceeding with {len(valid_queries)} valid queries.")
            if len(valid_queries) > TARGET_VALID_QUERIES:
                 valid_queries = valid_queries[:TARGET_VALID_QUERIES]

        if not valid_queries:
            logger.error("No valid queries found after all attempts.")
            return (
                ["[No valid queries found]"], 
                validation_attempts_count,
                [],
                []
            )
        
        brave_search_results_internal = await self.search_agent.aggregate_search(valid_queries)
        if self.url_extractor:
            extracted_candidates_list = self.url_extractor.extract_product_url_info(brave_search_results_internal)
        else:
            logger.error("self.url_extractor is None at the time of calling extract_product_url_info.")
            extracted_candidates_list = []
        
        if extracted_candidates_list:
            identified_page_candidates_list = await self.page_identifier.identify_batch_page_types(extracted_candidates_list, product)
        
        logger.debug(f"Returning from search_product. Type of identified_page_candidates_list: {type(identified_page_candidates_list)}")
        if isinstance(identified_page_candidates_list, list):
            logger.debug(f"Number of items in identified_page_candidates_list: {len(identified_page_candidates_list)}")
            for i, item in enumerate(identified_page_candidates_list):
                logger.debug(f"Item {i} in identified_page_candidates_list - Type: {type(item)}")
                if not isinstance(item, IdentifiedPageCandidate):
                    logger.error(f"Item {i} is NOT an IdentifiedPageCandidate instance! Content: {item}")
                # Optionally, log partial content if it is an IdentifiedPageCandidate
                # elif isinstance(item, IdentifiedPageCandidate):
                #     logger.debug(f"Item {i} (IdentifiedPageCandidate) - original_url_info.url: {item.original_url_info.url if item.original_url_info else 'None'}, page_type: {item.page_type}")
        else:
            logger.error(f"identified_page_candidates_list is NOT a list! Content: {identified_page_candidates_list}")

        return (
            valid_queries, 
            validation_attempts_count,
            extracted_candidates_list, 
            identified_page_candidates_list
        ) 