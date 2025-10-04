document.addEventListener('DOMContentLoaded', function() {
    const likeButtons = document.querySelectorAll('.like-btn');
    
    likeButtons.forEach(button => {
        button.addEventListener('click', function() {
            const postId = this.getAttribute('data-post-id');
            const heartIcon = this.querySelector('i');
            const likeCountSpan = this.querySelector('.like-count');
            
            fetch(`/user_side/like_post/${postId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': '{{ csrf_token }}',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Content-Type': 'application/json',
                },
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert('Error: ' + data.error);
                    return;
                }
                // Update heart icon
                if (data.is_liked) {
                    heartIcon.classList.add('text-danger');
                } else {
                    heartIcon.classList.remove('text-danger');
                }
                // Update like count
                likeCountSpan.textContent = `(${data.like_count})`;
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred while processing your request.');
            });
        });
    });
});