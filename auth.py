from functools import wraps

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect('/login')
        return func(*args, **kwargs)
    return wrapper