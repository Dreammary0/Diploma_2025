import os
import time

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy import event
from sqlalchemy.engine import Engine

from DataMovements.model import db, User, Datasets
from DataMovements.data_movements import fetch_datasets_for_user, delete_dataset_by_id
from Main.main import call_process_and_store_dataset, call_clustering, load_clustering_params, call_find_path, \
    load_graph_params


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'FeAF<j,f322AfHnE_VfCnB#'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'DB', 'TheWay.db')
db.init_app(app)
with app.app_context():
    db.create_all()

login_manager = LoginManager(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('index'))
        flash("Неверное имя пользователя или пароль")
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash("Пользователь с таким именем уже существует")
            return redirect(url_for('register'))
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('index'))
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


def get_coordinates(coords):
    lat, long = coords.split(',')
    return lat, long


@app.route('/post_graphs_parameters', methods=['POST'])
@login_required
def get_graph():
    parameters_for_graph = request.get_json()

    start_long, start_lat = get_coordinates(parameters_for_graph['start_coords'])
    end_lon, end_lat = get_coordinates(parameters_for_graph['end_coords'])
    coords = dict(start_lat=start_lat, start_lon=start_long, end_lat=end_lat, end_lon=end_lon)
    del parameters_for_graph['start_coords']
    del parameters_for_graph['end_coords']

    for key in parameters_for_graph:
        if key not in ('search_algorithm', 'points_inside', 'dataset_id'):
            parameters_for_graph[key] = float(parameters_for_graph[key])

    for key in coords:
        coords[key] = float(coords[key])

    cl_hash_id = session.get('cl_hash_id')
    if not cl_hash_id:
        return jsonify({"error": "Сначала необходимо выполнить кластеризацию."}), 400

    graph_data = call_find_path(parameters_for_graph, load_clustering_params(), coords, cl_hash_id)
    return jsonify(graph_data)


@app.route('/post_clustering_parameters', methods=['POST'])
@login_required
def get_clusters():
    start = time.time()
    parameters_for_clustering = request.get_json()
    clusters_data = call_clustering(parameters_for_clustering)
    session['cl_hash_id'] = clusters_data[3]
    print('Общее время прогона кластеризации с отрисовкой:', round(time.time() - start, 2), 'сек.')
    return jsonify(clusters_data)


@app.route('/get_datasets')
@login_required
def get_datasets():
    datasets = fetch_datasets_for_user(current_user.id)
    return jsonify(datasets)


@app.route('/choose_dataset', methods=['POST'])
@login_required
def choose_dataset():
    dataset_id = request.form.get('dataset_id')
    if not dataset_id:
        return jsonify(success=False, message='Датасет не выбран!')

    dataset = Datasets.query.filter_by(id=dataset_id).first()
    if not dataset:
        return jsonify(success=False, message='Датасет с таким id не найден!')

    return jsonify(success=True, message=f'Выбран датасет: {dataset.dataset_name}')


@app.route('/upload_dataset', methods=['POST'])
@login_required
def upload_dataset():
    file_positions = request.files.get('file-positions')
    file_marine = request.files.get('file-marine')
    dataset_name = request.form.get('dataset-name')
    interpolation = request.form.get('interpolation')
    max_gap_minutes = request.form.get('max_gap_minutes')
    user_id = current_user.id

    if not file_positions or not file_marine:
        return jsonify(success=False, message='Не выбраны оба файла!')

    success, message = call_process_and_store_dataset(file_positions,
                                                      file_marine,
                                                      dataset_name,
                                                      user_id,
                                                      interpolation,
                                                      max_gap_minutes)

    return jsonify(success=success, message=message)


@app.route('/delete_dataset', methods=['POST'])
@login_required
def delete_dataset():
    data = request.get_json()
    if not data or 'id' not in data:
        return jsonify(success=False, message='Неверный запрос: ID датасета отсутствует.')
    dataset_id_to_delete = data['id']
    current_user_id = current_user.id
    success, message = delete_dataset_by_id(dataset_id_to_delete, current_user_id)
    return jsonify(success=success, message=message)


@app.route('/')
@login_required
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    clustering_params = load_clustering_params()
    graph_params = load_graph_params()

    datasets = fetch_datasets_for_user(current_user.id)
    return render_template('index.html',
                           datasets=datasets,
                           clustering_params=clustering_params,
                           graph_params=graph_params,
                           int=int,
                           len=len
                           )


if __name__ == '__main__':
    app.run()
