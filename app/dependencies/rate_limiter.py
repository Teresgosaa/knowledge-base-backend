import asyncio

from fastapi import HTTPException, status

from app.service.s3_service import AsyncS3Service


# Dependency to get S3 service instance
async def get_s3_service() -> AsyncS3Service:
    service = AsyncS3Service()
    try:
        yield service
    finally:
        await service.close()


# Dependency for rate limiting (simple example)
class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests = {}

    async def __call__(self, client_ip: str):
        current_time = asyncio.get_event_loop().time()

        # Clean old requests
        self.requests[client_ip] = [
            req_time
            for req_time in self.requests.get(client_ip, [])
            if current_time - req_time < 60
        ]

        # Check rate limit
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )

        # Add current request
        self.requests[client_ip].append(current_time)


# Create rate limiter instance
rate_limiter = RateLimiter(requests_per_minute=100)

# end file
