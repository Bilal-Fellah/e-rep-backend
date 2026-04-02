from api.repositories.post_repository import PostRepository


class PostService:
    @staticmethod
    def get_post(page_id, platform, post_id):
        return PostRepository.get_by_composite_key(page_id, platform, post_id)

    @staticmethod
    def get_posts_by_platform(platform):
        return PostRepository.get_by_platform(platform)

    @staticmethod
    def get_posts_by_page(page_id, platform=None):
        return PostRepository.get_by_page(page_id, platform)

    @staticmethod
    def get_posts_by_entity(entity_id, platform=None):
        return PostRepository.get_by_entity(entity_id, platform)

    @staticmethod
    def get_post_history(page_id, platform, post_id):
        return PostRepository.get_post_history(page_id, platform, post_id)