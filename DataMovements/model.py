from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import JSON, ForeignKeyConstraint
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    # Связь настроена для быстрого каскадного удаления
    datasets = db.relationship('Datasets', back_populates='user', cascade="all, delete-orphan", passive_deletes=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Hashes(db.Model):
    __tablename__ = 'hashes'
    hash_id = db.Column(db.Integer, primary_key=True)
    hash_value = db.Column(db.String(64), unique=True, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    params = db.Column(JSON, nullable=True)

    # Связи, где этот хэш является "родителем"
    positions = db.relationship('PositionsCleaned', back_populates='source_hash', cascade="all, delete-orphan",
                                passive_deletes=True)
    clusters = db.relationship('Clusters', back_populates='hash', cascade="all, delete-orphan", passive_deletes=True)

    # ИЗМЕНЕНО: Связь с таблицей-ассоциацией
    source_of_datasets = db.relationship('Datasets', back_populates='source_hash', cascade="all, delete-orphan",
                                         passive_deletes=True)
    analysis_links = db.relationship('DatasetAnalysisLink', back_populates='analysis_hash',
                                     cascade="all, delete-orphan", passive_deletes=True)


class Datasets(db.Model):
    __tablename__ = 'datasets'
    id = db.Column(db.Integer, primary_key=True)
    dataset_name = db.Column(db.String(64), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    source_hash_id = db.Column(db.Integer, db.ForeignKey('hashes.hash_id', ondelete='CASCADE'), nullable=False)

    user = db.relationship('User', back_populates='datasets')
    source_hash = db.relationship('Hashes', back_populates='source_of_datasets', foreign_keys=[source_hash_id])

    # ИЗМЕНЕНО: Связь с таблицей-ассоциацией
    analysis_links = db.relationship('DatasetAnalysisLink', back_populates='dataset', cascade="all, delete-orphan",
                                     passive_deletes=True)


# --- НОВЫЙ КЛАСС ДЛЯ ТАБЛИЦЫ-СВЯЗКИ ---
class DatasetAnalysisLink(db.Model):
    __tablename__ = 'dataset_analysis_link'
    dataset_id = db.Column(db.Integer, db.ForeignKey('datasets.id', ondelete='CASCADE'), primary_key=True)
    analysis_hash_id = db.Column(db.Integer, db.ForeignKey('hashes.hash_id', ondelete='CASCADE'), primary_key=True)

    dataset = db.relationship('Datasets', back_populates='analysis_links')
    analysis_hash = db.relationship('Hashes', back_populates='analysis_links')


class PositionsCleaned(db.Model):
    __tablename__ = 'positions_cleaned'
    position_id = db.Column(db.Integer, primary_key=True)
    hash_id = db.Column(db.Integer, db.ForeignKey('hashes.hash_id', ondelete='CASCADE'), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    speed = db.Column(db.Float)
    course = db.Column(db.Float)

    source_hash = db.relationship('Hashes', back_populates='positions')
    cluster_membership = db.relationship('ClusterMembers', back_populates='position', uselist=False,
                                         cascade="all, delete-orphan", passive_deletes=True)


class Clusters(db.Model):
    __tablename__ = 'clusters'
    hash_id = db.Column(db.Integer, db.ForeignKey('hashes.hash_id', ondelete='CASCADE'), primary_key=True)
    cluster_num = db.Column(db.Integer, primary_key=True)

    hash = db.relationship('Hashes', back_populates='clusters')
    members = db.relationship('ClusterMembers', back_populates='cluster', cascade="all, delete-orphan",
                              passive_deletes=True)
    avg_values = db.relationship('ClAverageValues', back_populates='cluster', uselist=False,
                                 cascade="all, delete-orphan", passive_deletes=True)
    polygons = db.relationship('ClPolygons', back_populates='cluster', cascade="all, delete-orphan",
                               passive_deletes=True)
    graphs = db.relationship('Graphs', back_populates='cluster', cascade="all, delete-orphan", passive_deletes=True)


# --- "СОСТАВ КЛАСТЕРА": Таблица-связка между позициями и кластерами ---
class ClusterMembers(db.Model):
    __tablename__ = 'cluster_members'
    hash_id = db.Column(db.Integer, primary_key=True)
    cluster_num = db.Column(db.Integer, primary_key=True)
    position_id = db.Column(db.Integer, db.ForeignKey('positions_cleaned.position_id', ondelete='CASCADE'),
                            primary_key=True)

    # Композитный внешний ключ к таблице Clusters
    __table_args__ = (
        ForeignKeyConstraint(['hash_id', 'cluster_num'], ['clusters.hash_id', 'clusters.cluster_num'],
                             ondelete='CASCADE'),
    )

    cluster = db.relationship('Clusters', back_populates='members')
    position = db.relationship('PositionsCleaned', back_populates='cluster_membership')


# --- Данные, относящиеся к кластеру ---

class ClAverageValues(db.Model):
    __tablename__ = 'cl_average_values'
    hash_id = db.Column(db.Integer, primary_key=True)
    cluster_num = db.Column(db.Integer, primary_key=True)
    average_speed = db.Column(db.Float)
    average_course = db.Column(db.Float)

    __table_args__ = (
        ForeignKeyConstraint(['hash_id', 'cluster_num'], ['clusters.hash_id', 'clusters.cluster_num'],
                             ondelete='CASCADE'),)
    cluster = db.relationship('Clusters', back_populates='avg_values')


class ClPolygons(db.Model):
    __tablename__ = 'cl_polygons'
    polygon_point_id = db.Column(db.Integer, primary_key=True)
    hash_id = db.Column(db.Integer, nullable=False)
    cluster_num = db.Column(db.Integer, nullable=False)
    x = db.Column(db.Float, nullable=False)
    y = db.Column(db.Float, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(['hash_id', 'cluster_num'], ['clusters.hash_id', 'clusters.cluster_num'],
                             ondelete='CASCADE'),)
    cluster = db.relationship('Clusters', back_populates='polygons')


class Graphs(db.Model):
    __tablename__ = 'graphs'
    graph_id = db.Column(db.Integer, primary_key=True)
    hash_id = db.Column(db.Integer, nullable=False)
    cluster_num = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(['hash_id', 'cluster_num'], ['clusters.hash_id', 'clusters.cluster_num'],
                             ondelete='CASCADE'),)
    cluster = db.relationship('Clusters', back_populates='graphs')

    vertexes = db.relationship('GraphVertexes', back_populates='graph', cascade="all, delete-orphan",
                               passive_deletes=True)
    edges = db.relationship('GraphEdges', back_populates='graph', cascade="all, delete-orphan", passive_deletes=True)


# Модели графа остаются почти без изменений, их связи с Graphs корректны
class GraphVertexes(db.Model):
    __tablename__ = 'graph_vertexes'
    vertex_id = db.Column(db.Integer, primary_key=True)
    graph_id = db.Column(db.Integer, db.ForeignKey('graphs.graph_id', ondelete='CASCADE'), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    graph = db.relationship('Graphs', back_populates='vertexes')
    edges_start = db.relationship('GraphEdges', back_populates='start_vertex',
                                  foreign_keys='GraphEdges.start_vertex_id', cascade="all, delete-orphan",
                                  passive_deletes=True)
    edges_end = db.relationship('GraphEdges', back_populates='end_vertex', foreign_keys='GraphEdges.end_vertex_id',
                                cascade="all, delete-orphan", passive_deletes=True)


class GraphEdges(db.Model):
    __tablename__ = 'graph_edges'
    edge_id = db.Column(db.Integer, primary_key=True)
    start_vertex_id = db.Column(db.Integer, db.ForeignKey('graph_vertexes.vertex_id', ondelete='CASCADE'),
                                nullable=False)
    end_vertex_id = db.Column(db.Integer, db.ForeignKey('graph_vertexes.vertex_id', ondelete='CASCADE'), nullable=False)
    weight = db.Column(db.Float)
    graph_id = db.Column(db.Integer, db.ForeignKey('graphs.graph_id', ondelete='CASCADE'), nullable=False)

    start_vertex = db.relationship('GraphVertexes', foreign_keys=[start_vertex_id], back_populates='edges_start')
    end_vertex = db.relationship('GraphVertexes', foreign_keys=[end_vertex_id], back_populates='edges_end')
    graph = db.relationship('Graphs', back_populates='edges')
    routes = db.relationship('Routes', back_populates='edge', cascade="all, delete-orphan", passive_deletes=True)


class Routes(db.Model):
    __tablename__ = 'routes'
    route_id = db.Column(db.Integer, primary_key=True)
    edge_id = db.Column(db.Integer, db.ForeignKey('graph_edges.edge_id', ondelete='CASCADE'), nullable=False)

    edge = db.relationship('GraphEdges', back_populates='routes')
