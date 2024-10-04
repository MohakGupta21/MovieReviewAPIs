from flask import Flask,jsonify,request
from flask_cors import CORS, cross_origin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase,Mapped, mapped_column
from datetime import datetime
from flask_migrate import Migrate


app = Flask(__name__)
CORS(app)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)


app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///project.db"
migrate = Migrate(app,db)
db.init_app(app)

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, unique=True, nullable=False)
    release_date = db.Column(db.String, nullable=False)
    avg_rating = db.Column(db.Integer,default=0, nullable=False)
    reviews = db.relationship('Review',backref='movie',lazy=True, cascade="all, delete-orphan")
    __table_args__ = (
        db.CheckConstraint('avg_rating <= 10', name='check_max_value'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'release_date': self.release_date,
            'avg_rating': self.avg_rating,
            'reviews': [review.to_dict() for review in self.reviews]
        }
    
class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True,autoincrement=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'),nullable=False)
    reviewer = db.Column(db.String,nullable=True)
    rating = db.Column(db.Integer, nullable=False)
    comments = db.Column(db.String, nullable=False)
    __table_args__ = (
        db.CheckConstraint('rating <= 10', name='check_rating_value'),
    )
    def to_dict(self):
        return {
            'id': self.id,
            'reviewer': self.reviewer,
            'rating': self.rating,
            'comments': self.comments,
        }
with app.app_context():
    db.create_all()

@app.teardown_appcontext
def shutdown_session(exception=None):
    """Ensure that the db session is closed after each request."""
    db.session.remove()


@app.route("/movies")
def getMovies():
    try:
        allMovies = Movie.query.all()
        movie_list = [movie.to_dict() for movie in allMovies]
        # print(movie_list)
        return jsonify(movie_list),201
    except Exception as e:
        db.session.rollback()  # Rollback in case of an error
        return jsonify({'error',str(e)}),500

@app.route("/addMovie",methods=['POST'])
def addMovie():
    try:
        data = request.get_json()
        new_movie = Movie(name=data.get('name'),release_date=data.get('release_date'))
        db.session.add(new_movie)
        db.session.commit()
        return {'message': 'movie added'}, 201  # Return 201 status code
    except Exception as e:
        db.session.rollback()  # Rollback in case of an error
        return jsonify({'error':str(e)}),500


@app.route('/updateMovie/<int:sno>', methods=['PUT','OPTIONS'])
@cross_origin()
def update(sno):
    try:
        if request.method =="OPTIONS":
            return {'message':'end_reached'},200
        data = request.get_json()

        # Get the movie by its ID
        movie = Movie.query.get_or_404(sno)

        # Update the movie details with new data from request
        movie.name = data.get('name')
        movie.release_date = data.get('release_date')

        # Save changes to the database
        db.session.add(movie)
        db.session.commit()

        return {'message': 'Movie updated successfully'}, 200

    except Exception as e:
        db.session.rollback()  # Rollback in case of an error
        return jsonify({'error': str(e)}), 500

@app.route('/deleteMovie/<int:sno>',methods=['DELETE'])
def delete(sno):
    try:
        movie = Movie.query.get_or_404(sno)
        if not movie:
            return jsonify({"error": "Movie not found"}), 404

        db.session.delete(movie)
        db.session.commit()

        return {'message':'movie deleted'}, 200
    except Exception as e:
        db.session.rollback()  # Rollback in case of an error
        return jsonify({'error':str(e)}),500

def update_movie_avg_rating(movie_id):
    try:
        # Get all reviews for the movie
        all_reviews = Review.query.filter_by(movie_id=movie_id).all()
        
        if all_reviews:
            total_reviews = len(all_reviews)
            total_rating = sum([review.rating for review in all_reviews])
            new_avg_rating = total_rating / total_reviews
            movie = Movie.query.get(movie_id)
            movie.avg_rating = round(new_avg_rating, 2)  # Update movie's average rating
        else:
            # If there are no reviews left, set avg_rating to 0
            movie = Movie.query.get(movie_id)
            movie.avg_rating = 0
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e


@app.route('/addReview',methods=['POST'])
def addReview():
    data = request.get_json()

    try:
        movie_name = data.get('movie')
        rating = int(data.get('rating'))
        reviewer = data.get('reviewer')  # Default reviewer if not provided
        comments = data.get('comments')

        if reviewer=="" or reviewer==None:
            reviewer = "Anonymous"
        # Validate rating
        if not 0 <= rating <= 10:
            return jsonify({"error": "Rating must be between 0 and 10."}), 400

        # Find the movie by name
        movie = Movie.query.filter_by(name=movie_name).first()

        if not movie:
            return jsonify({"error": "Movie not found"}), 404
    
        # Add the new review
        new_review = Review(movie_id=movie.id, rating=rating, reviewer=reviewer, comments=comments)
        db.session.add(new_review)

        # Commit to database so that the review is saved first
        db.session.commit()

        # Update the average rating of the movie
        all_reviews = Review.query.filter_by(movie_id=movie.id).all()
        total_reviews = len(all_reviews)
        total_rating = sum([review.rating for review in all_reviews])
        new_avg_rating = total_rating / total_reviews  # Integer division to round down
        movie.avg_rating = round(new_avg_rating,2)
        db.session.commit()

        return jsonify({"message": "Review added successfully", "new_avg_rating": new_avg_rating}), 201


    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/getReviews/<int:movie_id>', methods=['GET'])
def get_reviews(movie_id):
    try:
        # Get the movie by its ID
        movie = Movie.query.get_or_404(movie_id)

        # Get all reviews for the movie
        reviews = Review.query.filter_by(movie_id=movie.id).all()

        # Format the reviews for the response
        reviews_list = [review.to_dict() for review in reviews]

        return jsonify({"movie": movie.name, "reviews": reviews_list}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/editReview/<int:review_id>', methods=['PUT'])
def edit_review(review_id):
    try:
        # Get the review by its ID
        review = Review.query.get_or_404(review_id)

        # Get the new data from the request
        data = request.get_json()
        new_rating = data.get('rating', review.rating)
        new_comments = data.get('comments', review.comments)
        new_reviewer = data.get('reviewer', review.reviewer)

        # Validate the new rating
        if not 0 <= new_rating <= 10:
            return jsonify({"error": "Rating must be between 0 and 10."}), 400

        # Update the review
        review.rating = new_rating
        review.comments = new_comments
        review.reviewer = new_reviewer
        db.session.commit()

        # Update the movie's average rating
        update_movie_avg_rating(review.movie_id)

        return jsonify({"message": "Review updated successfully"}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/getReview/<int:review_id>',methods=['GET'])
def get_review_by_id(review_id):
    try:
        review = Review.query.get_or_404(review_id)
        reviewDict = review.to_dict()
        return jsonify(reviewDict),200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/getMovie/<int:movie_id>',methods=['GET'])
def get_movie_by_id(movie_id):
    try:
        movie = Movie.query.get_or_404(movie_id)
        movieDict = movie.to_dict()

        return jsonify(movieDict),200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/deleteReview/<int:review_id>', methods=['DELETE'])
def delete_review(review_id):
    try:
        # Get the review by its ID
        review = Review.query.get_or_404(review_id)

        # Save the movie ID to update its average rating after deletion
        movie_id = review.movie_id

        # Delete the review
        db.session.delete(review)
        db.session.commit()

        # Update the movie's average rating
        update_movie_avg_rating(movie_id)

        return jsonify({"message": "Review deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


if __name__=='__main__':
    app.run(debug=True,port=5001)