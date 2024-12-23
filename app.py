import json

from flask import Flask, request, jsonify, make_response, Response, request
from flask_sqlalchemy import SQLAlchemy
from movie_collection.db import db
from movie_collection.models.user_model import Users

from movie_collection.models.movie_model import (
    Movie, 
    find_movie_by_name,
    find_movie_by_year,
    find_movie_by_language,
    find_movie_by_director,
    find_movie_by_genre,
    add_movie_to_list,
    delete_movie_from_list,
    clear_movie_list,
    mark_movie_as_favorite,
    list_favorite_movies
)

from movie_collection.utils.sql_utils import check_database_connection, check_table_exists

import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

##########################################################
#
# Health Check
#
##########################################################

@app.route('/api/health', methods=['GET'])
def healthcheck() -> Response:
    """
    Health check route to verify the service is running.

    Returns:
        JSON Response: {"status": "healthy"}, 200
    """
    logger.info('Health check requested')
    return make_response(jsonify({'status': 'healthy'}), 200)

@app.route('/api/db-check', methods=['GET'])
def db_check() -> Response:
    """
    Route to check if the database connection and movies table are functional.

    Returns:
        JSON response indicating the database health status.
    Raises:
        404 error if there is an issue with the database.
    """
    try:
        app.logger.info("Checking database connection...")
        check_database_connection()
        app.logger.info("Database connection is OK.")
        app.logger.info("Checking if movies table exists...")
        check_table_exists("movies")
        app.logger.info("movies table exists.")
        return make_response(jsonify({'database_status': 'healthy'}), 200)
    except Exception as e:
        return make_response(jsonify({'error': str(e)}), 404)

##########################################################
#
# User Management
#
##########################################################

@app.route('/create-account', methods=['POST'])
def create_account():
    """
    Create a new user account with secure password storage.

    Expected JSON Input:
        - username (str): The username for the new user
        - password (str): The password to be hashed and stored

    Returns:
        JSON Response:
            - success: {"status": "success", "message": "Account created successfully"}, 201
            - error: {"error": error_message}, status_code

    Raises:
        400: If input validation fails
        500: If there is an issue adding the user to the database
    """
    logger.info('Creating new account')
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        logger.error('Missing username or password in request')
        return make_response(jsonify({'error': 'Invalid input, both username and password are required'}), 400)
    
    try:
        Users.create_user(username, password)
        logger.info('Account created successfully for user: %s', username)
        return make_response(jsonify({'status': 'success', 'message': 'Account created successfully'}), 201)
    except ValueError as e:
        logger.error('Value error during account creation: %s', str(e))
        return make_response(jsonify({'error': str(e)}), 400)
    except Exception as e:
        logger.error('Unexpected error during account creation: %s', str(e))
        return make_response(jsonify({'error': 'An error occurred while creating the account'}), 500)

@app.route('/login', methods=['POST'])
def login():
    """
    Verify user credentials against stored password hash.

    Expected JSON Input:
        - username (str): The username of the user
        - password (str): The password to verify

    Returns:
        JSON Response:
            - success: {"status": "success", "message": "Login successful"}, 200
            - error: {"error": error_message}, status_code

    Raises:
        400: If input validation fails
        401: If authentication fails
        404: If user not found
    """
    logger.info('Processing login request')
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        logger.error('Missing username or password in login request')
        return make_response(jsonify({'error': 'Invalid input, both username and password are required'}), 400)
    
    try:
        if Users.check_password(username, password):
            logger.info('Login successful for user: %s', username)
            return make_response(jsonify({'status': 'success', 'message': 'Login successful'}), 200)
        logger.warning('Failed login attempt for user: %s', username)
        return make_response(jsonify({'error': 'Invalid credentials'}), 401)
    except ValueError as e:
        logger.error('Value error during login: %s', str(e))
        return make_response(jsonify({'error': str(e)}), 404)
    except Exception as e:
        logger.error('Unexpected error during login: %s', str(e))
        return make_response(jsonify({'error': 'An error occurred during login'}), 500)

@app.route('/update-password', methods=['POST'])
def update_password():
    """
    Update a user's password after verifying their current password.

    Expected JSON Input:
        - username (str): The username of the user
        - old_password (str): The current password
        - new_password (str): The new password to set

    Returns:
        JSON Response:
            - success: {"status": "success", "message": "Password updated successfully"}, 200
            - error: {"error": error_message}, status_code

    Raises:
        400: If input validation fails
        401: If old password is invalid
        404: If user not found
    """
    logger.info('Processing password update request')
    data = request.get_json()
    username = data.get('username')
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    
    if not username or not old_password or not new_password:
        logger.error('Missing required fields in password update request')
        return make_response(jsonify({'error': 'Username, old password, and new password are required'}), 400)
    
    try:
        if Users.check_password(username, old_password):
            Users.update_password(username, new_password)
            logger.info('Password updated successfully for user: %s', username)
            return make_response(jsonify({'status': 'success', 'message': 'Password updated successfully'}), 200)
        logger.warning('Invalid old password provided for user: %s', username)
        return make_response(jsonify({'error': 'Invalid old password'}), 401)
    except ValueError as e:
        logger.error('Value error during password update: %s', str(e))
        return make_response(jsonify({'error': str(e)}), 404)
    except Exception as e:
        logger.error('Unexpected error during password update: %s', str(e))
        return make_response(jsonify({'error': 'An error occurred while updating the password'}), 500)

##########################################################
#
# Movie Management
#
##########################################################

@app.route('/movies/search-by-name', methods=['POST'])
def search_by_name():
    """
    Search for a movie by name.

    Expected Query Parameters:
        - name (str): The name of the movie to search for

    Returns:
        JSON Response:
            - success: Movie details, 200
            - error: {"error": error_message}, status_code
    """
    logger.info('Processing movie search by name request')
    data = request.get_json()
    name = data.get('name')
    
    if not name:
        logger.error('Missing movie name in request')
        return make_response(jsonify({'error': 'Movie name is required'}), 400)
    
    try:
        movie = find_movie_by_name(name)
        logger.info('Movie found: %s', movie.name)
        return make_response(jsonify({
            'status': 'success',
            'name': movie.name,
            'year': movie.year,
            'director': movie.director,
            'genres': movie.genres,
            'original_language': movie.original_language
        }), 200)
    except ValueError as e:
        logger.error('Value error during movie search: %s', str(e))
        return make_response(jsonify({'error': str(e)}), 404)
    except Exception as e:
        logger.error('Unexpected error during movie search: %s', str(e))
        return make_response(jsonify({'error': 'An error occurred while searching for the movie'}), 500)

@app.route('/movies/search-by-year', methods=['POST'])
def search_by_year():
    """
    Get a random movie from a specific year.

    Expected Query Parameters:
        - year (int): The year to search for

    Returns:
        JSON Response:
            - success: Movie details, 200
            - error: {"error": error_message}, status_code
    """
    logger.info('Processing random movie by year request')
    try:
        data = request.get_json()
        year = int(data.get('year'))
    except ValueError:
        logger.error('Invalid year format provided')
        return make_response(jsonify({'error': 'Year must be a valid integer'}), 400)
    
    if year < 1900:
        logger.error('Invalid year provided: %d', year)
        return make_response(jsonify({'error': 'Year must be 1900 or later'}), 400)
    
    try:
        movie = find_movie_by_year(year)
        logger.info('Movie found: %s', movie.name)
        return make_response(jsonify({
            'status': 'success',
            'name': movie.name,
            'year': movie.year,
            'director': movie.director,
            'genres': movie.genres,
            'original_language': movie.original_language
        }), 200)
    except ValueError as e:
        logger.error('Value error during movie search: %s', str(e))
        return make_response(jsonify({'error': str(e)}), 404)
    except Exception as e:
        logger.error('Unexpected error during movie search: %s', str(e))
        return make_response(jsonify({'error': 'An error occurred while searching for the movie'}), 500)

@app.route('/movies/search-by-language', methods=['POST'])
def search_by_language():
    """
    Search for movies by original language.

    Expected Query Parameters:
        - language_code (str): The language code to search for

    Returns:
        JSON Response:
            - success: Movie details, 200
            - error: {"error": error_message}, status_code
    """
    logger.info('Processing movie search by language request')
    data = request.get_json()
    language_code = data.get('language_code')
    
    if not language_code:
        logger.error('Missing language code in request')
        return make_response(jsonify({'error': 'Language code is required'}), 400)
    
    try:
        movie = find_movie_by_language(language_code)
        logger.info('Movie found: %s', movie.name)
        return make_response(jsonify({
            'status': 'success',
            'name': movie.name,
            'year': movie.year,
            'director': movie.director,
            'genres': movie.genres,
            'original_language': movie.original_language
        }), 200)
    except ValueError as e:
        logger.error('Value error during movie search: %s', str(e))
        return make_response(jsonify({'error': str(e)}), 404)
    except Exception as e:
        logger.error('Unexpected error during movie search: %s', str(e))
        return make_response(jsonify({'error': 'An error occurred while searching for the movie'}), 500)

@app.route('/movies/search-by-director', methods=['POST'])
def search_by_director():
    """
    Search for movies by director name.

    Expected Query Parameters:
        - director (str): The name of the director to search for

    Returns:
        JSON Response:
            - success: Movie details, 200
            - error: {"error": error_message}, status_code
    """
    logger.info('Processing movie search by director request')    
    data = request.get_json()
    director = data.get('director')
    
    if not director:
        logger.error('Missing director name in request')
        return make_response(jsonify({'error': 'Director name is required'}), 400)
    
    try:
        movie = find_movie_by_director(director)
        logger.info('Movie found: %s', movie.name)
        return make_response(jsonify({
            'status': 'success',
            'name': movie.name,
            'year': movie.year,
            'director': movie.director,
            'genres': movie.genres,
            'original_language': movie.original_language
        }), 200)
    except ValueError as e:
        logger.error('Value error during movie search: %s', str(e))
        return make_response(jsonify({'error': str(e)}), 404)
    except Exception as e:
        logger.error('Unexpected error during movie search: %s', str(e))
        return make_response(jsonify({'error': 'An error occurred while searching for the movie'}), 500)

@app.route('/movies/search-by-genre', methods=['POST'])
def search_by_genre():
    """
    Search for movies by genre ID.

    Expected Query Parameters:
        - genre_id (int): The ID of the genre to search for

    Returns:
        JSON Response:
            - success: Movie details, 200
            - error: {"error": error_message}, status_code
    """
    logger.info('Processing movie search by genre request')

    try:
        data = request.get_json()
        genre_id = int(data.get('genre_id'))
    except ValueError:
        logger.error('Invalid genre ID format provided')
        return make_response(jsonify({'error': 'Genre ID must be a valid integer'}), 400)
    
    if genre_id <= 0:
        logger.error('Invalid genre ID provided: %d', genre_id)
        return make_response(jsonify({'error': 'Genre ID must be a positive integer'}), 400)
    
    try:
        movie = find_movie_by_genre(genre_id)
        logger.info('Movie found: %s', movie.name)
        return make_response(jsonify({
            'status': 'success',
            'name': movie.name,
            'year': movie.year,
            'director': movie.director,
            'genres': movie.genres,
            'original_language': movie.original_language
        }), 200)
    except ValueError as e:
        logger.error('Value error during movie search: %s', str(e))
        return make_response(jsonify({'error': str(e)}), 404)
    except Exception as e:
        logger.error('Unexpected error during movie search: %s', str(e))
        return make_response(jsonify({'error': 'An error occurred while searching for the movie'}), 500)
    
@app.route('/movies/add-to-list', methods=['POST'])
def add_to_list():
    """
    Add a movie to the database.

    Expected Query Parameters:
        name (str): The name of the movie.
        year (int): The release year of the movie.
        director (str): The director of the movie.
        genres (list): A list of genres associated with the movie.
        original_language (str): The original language of the movie.
        favorite (bool, optional): Whether the movie is marked as a favorite. Defaults to False.

    Returns:
        JSON Response:
            - success: Movie details, 200
            - error: {"error": error_message}, status_code
    """
    logger.info('Adding movie to the database')
    
    data = request.get_json()

    name = data.get('name')
    
    if not name:
        logger.error('Missing movie name in request')
        return make_response(jsonify({'error': 'Movie name is required'}), 400)
    
    try:
        year = int(data.get('year'))
    except ValueError:
        logger.error('Invalid year format provided')
        return make_response(jsonify({'error': 'Year must be a valid integer'}), 400)
    
    if year < 1900:
        logger.error('Invalid year provided: %d', year)
        return make_response(jsonify({'error': 'Year must be 1900 or later'}), 400)
    
    language_code = data.get('language_code')
    
    if not language_code:
        logger.error('Missing language code in request')
        return make_response(jsonify({'error': 'Language code is required'}), 400)

    director = data.get('director')
    
    if not director:
        logger.error('Missing director name in request')
        return make_response(jsonify({'error': 'Director name is required'}), 400)
    
    genres = data.get('genres')

    if not genres:
        logger.error('Missing genres in request')
        return make_response(jsonify({'error': 'Genre is required'}), 400)

    favorite = data.get('favorite')

    if favorite == 'True':
        favorite = True
    else:
        favorite = False
    
    try:
        add_movie_to_list(name, year, director, genres, language_code, favorite)
        logger.info('Movie added: %s', name)
        return make_response(jsonify({
            'status': 'success'
        }), 200)
    except ValueError as e:
        logger.error('Value error: %s', str(e))
        return make_response(jsonify({'error': str(e)}), 404)
    except Exception as e:
        logger.error('Unexpected error: %s', str(e))
        return make_response(jsonify({'error': 'An error occurred while adding movie to the database'}), 500)
    
@app.route('/movies/delete-from-list', methods=['DELETE'])
def delete_from_list():
    """
    Soft deletes a movie from the catalog by marking it as deleted.

    Expected Query Parameters:
        movie_id (int): The ID of the movie to delete.

    Returns:
        JSON Response:
            - success: {"status": "success"}, 200
            - error: {"error": error_message}, status_code
    """
    logger.info('Deleting movie from the database')
    
    data = request.get_json()
    
    try:
        movie_id = int(data.get('movie_id'))
    except ValueError:
        logger.error('Invalid movie_id format provided')
        return make_response(jsonify({'error': 'Year must be a valid integer'}), 400)
    
    try:
        delete_movie_from_list(movie_id)
        logger.info('Movie deleted: %d', movie_id)
        return make_response(jsonify({
            'status': 'success'
        }), 200)
    except ValueError as e:
        logger.error('Value error: %s', str(e))
        return make_response(jsonify({'error': str(e)}), 404)
    except Exception as e:
        logger.error('Unexpected error: %s', str(e))
        return make_response(jsonify({'error': 'An error occurred while deleting movie from the database'}), 500)

@app.route('/movies/clear-list', methods=['DELETE'])
def clear_list():
    """
    Recreates the movie table, effectively deleting all movies.

    Returns:
        JSON Response:
            - success: {"status": "success"}, 200
            - error: {"error": error_message}, status_code
    """
    try:
        clear_movie_list()
        logger.info('Clearing Database')
        return make_response(jsonify({
            'status': 'success'
        }), 200)
    except ValueError as e:
        logger.error('Value error: %s', str(e))
        return make_response(jsonify({'error': str(e)}), 404)
    except Exception as e:
        logger.error('Unexpected error: %s', str(e))
        return make_response(jsonify({'error': 'An error occurred while clearing the database'}), 500)
    
@app.route('/movies/mark-as-favorite', methods=['POST'])
def mark_as_favorite():
    """
    Marks a movie as a favorite in the database.

    Expected Query Parameters:
        name (str): The name of the movie to mark as favorite.

    Returns:
        JSON Response:
            - success: {"status": "success"}, 200
            - error: {"error": error_message}, status_code
    """
    data = request.get_json()
    name = data.get('name')

    try:
        mark_movie_as_favorite(name)
        logger.info('Marking %s as favorite', name)
        return make_response(jsonify({
            'status': 'success'
        }), 200)
    except ValueError as e:
        logger.error('Value error: %s', str(e))
        return make_response(jsonify({'error': str(e)}), 404)
    except Exception as e:
        logger.error('Unexpected error: %s', str(e))
        return make_response(jsonify({'error': 'An error occurred while marking a movie favorite'}), 500)
    
@app.route('/movies/list-favorite', methods=['GET'])
def list_favorite() -> list:
    """
    Fetches the names of all favorite movies from the database.

    Returns:
        JSON Response:
            - success: Movie List, 200
            - error: {"error": error_message}, status_code
    """
    try:
        logger.info('Retriving Favorites')
        favorite_movies = list_favorite_movies()
        return make_response(jsonify({
            'status': 'success',
            'favorite_movies': json.dumps(favorite_movies)
        }), 200)
    except ValueError as e:
        logger.error('Value error: %s', str(e))
        return make_response(jsonify({'error': str(e)}), 404)
    except Exception as e:
        logger.error('Unexpected error: %s', str(e))
        return make_response(jsonify({'error': 'An error occurred while retriving favorite movies'}), 500)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        logger.info('Database tables created successfully')
    app.run(debug=True, host='0.0.0.0', port=5000)