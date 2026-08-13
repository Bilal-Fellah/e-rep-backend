# Business workflows for post service.
from api.repositories.post_repository import PostRepository
from api.services.posts_created_at_service import PostsCreatedAtService
from api.utils.logging_utils import instrument_service_class


@instrument_service_class
class PostService:
    @staticmethod
    def get_post(page_id, platform, post_id):
        """
        Get a single post by its composite key.
        
        If filling is enabled, automatically fills missing created_at dates in-memory.
        """
        post = PostRepository.get_by_composite_key(page_id, platform, post_id)
        
        if post:
            # Fill missing date in-memory before returning
            post = PostsCreatedAtService.fill_missing_date_for_post(post, page_id, platform, post_id)
        
        return post

    @staticmethod
    def get_posts_by_platform(platform):
        """Get all latest posts for a given platform."""
        posts = PostRepository.get_by_platform(platform)
        
        if posts:
            # Fill missing dates in-memory before returning
            posts = PostsCreatedAtService.fill_missing_dates_for_posts(posts)
        
        return posts

    @staticmethod
    def get_posts_by_page(page_id, platform=None):
        """
        Get all latest posts for a page, optionally filtered by platform.
        
        If filling is enabled, automatically fills missing created_at dates in-memory.
        """
        posts = PostRepository.get_by_page(page_id, platform)
        
        if posts:
            # Fill missing dates in-memory before returning
            posts = PostsCreatedAtService.fill_missing_dates_for_posts(posts)
        
        return posts

    @staticmethod
    def get_posts_by_entity(entity_id, platform=None):
        """Get all latest posts across every page belonging to an entity."""
        posts = PostRepository.get_by_entity(entity_id, platform)
        
        if posts:
            # Fill missing dates in-memory before returning
            posts = PostsCreatedAtService.fill_missing_dates_for_posts(posts)
        
        return posts

    @staticmethod
    def get_post_history(page_id, platform, post_id):
        """
        Get the full snapshot history of a single post from posts_history_mv.
        
        If filling is enabled, automatically fills missing created_at dates in-memory.
        """
        history = PostRepository.get_post_history(page_id, platform, post_id)
        
        if history:
            # Fill missing dates in-memory before returning
            history = PostsCreatedAtService.fill_missing_dates_for_post_history(history)
        
        return history
