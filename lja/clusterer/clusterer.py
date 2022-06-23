import os, sys
import numpy as np
from lja.analyser.plotter import Plotter
import matplotlib.pyplot as plt
import pandas as pd

from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_samples, silhouette_score
from sklearn.cluster import SpectralClustering
from sklearn.neighbors import kneighbors_graph
import scipy


class Clusterer:
    """Creates an clustering object, that clusters the read vectors of each layer."""

    def __init__(self, path, show_plots=False):
        super(Clusterer, self).__init__()
        self.path = path
        self.side = None
        self.u_list = []
        self.vh_list = []
        self.clusters = []
        self.number_of_clusters = []
        self.number_of_layers = None
        self.ks = []
        self.plotter = Plotter(path, show_plots)
        self.center_of_clusters = []

    def load_data(self, side="left"):
        # config
        self.side = side

        # Set path to decompositions
        path_folder = "results/decompositions/" + self.path + self.side
        print("Load decompositions from: ", path_folder)

        # Load decompsitions
        self.number_of_layers = len(next(os.walk(path_folder))[1])
        for layer in range(self.number_of_layers):
            path = path_folder + "/Layer" + str(layer) + "/"

            if self.side == "left":
                self.u_list.append(np.load(os.path.join(path, "u.npy")))
                self.ks.append(self.u_list[0].shape[2])

            elif self.side == "right":
                self.vh_list.append(np.load(os.path.join(path, "vh.npy")))
                self.ks.append(self.vh_list[0].shape[2])

        pass

    def store(self):
        # Set path to decompositions
        path_folder = "results/decompositions/" + self.path + self.side
        print("\nStore in: ", path_folder)

        # layers, vectors, num_clusters, 1024
        # Store clusters
        for layer in range(self.number_of_layers):
            newpath = path_folder + "/Layer" + str(layer) + "/"

            # (1)
            np.save(newpath + "number_of_clusters.npy", self.number_of_clusters[layer])

            # (k, n)
            np.save(newpath + "clusters.npy", self.clusters[layer])

            # (k, n, dim)
            np.save(
                newpath + "center_of_clusters.npy",
                np.array(self.center_of_clusters[layer], dtype=object),
            )

        pass

    def format_vectors(self, layer, k):
        if self.side == "left":
            vectors = self.u_list[layer]
            vectors = np.transpose(
                vectors, (0, 2, 1)
            )  # [sample, vector_index, next_dimension]
            vectors = vectors[:, :k, :]
            vectors = vectors.reshape(vectors.shape[0] * vectors.shape[1], -1)

        elif self.side == "right":
            vectors = self.vh

        return vectors

    def format_cluster_labels(self, labels, layer, k):
        if self.side == "left":
            vectors = self.u_list[layer]
            vectors = vectors[:, :, :k]
            labels = labels.reshape(vectors.shape[0], vectors.shape[2])

        elif self.side == "right":
            vectors = self.vh

        return labels

    def cluster_all_vectors(self, k=5, plot=True):
        for layer in range(self.number_of_layers):

            print("\n\n --- Layer: ", layer)

            # 1. Find number of clusters
            vectors = vectors = self.format_vectors(layer, k)
            n_clusters, affinity_matrix = self.find_number_of_clusters(
                vectors, layer, plot=plot
            )
            self.number_of_clusters.append(n_clusters)

            # 2. Clustering
            cluster_labels = self.cluster_vectors(
                vectors, layer, affinity_matrix, n_clusters
            )
            self.clusters.append(self.format_cluster_labels(cluster_labels, layer, k))

            # 3. Compute centers
            centers = self.get_center_of_clusters(
                vectors, layer, cluster_labels, n_clusters
            )
            self.center_of_clusters.append(centers)

        pass

    def get_center_of_clusters(self, vectors, layer, cluster_labels, n_clusters):

        # data
        centers = []

        # loop thorugh clusters
        for label in range(n_clusters):
            mask = cluster_labels == label
            cluster = vectors[mask, :]
            center = np.mean(cluster, axis=0)  #  mean center
            centers.append(center)

        return centers

    def cluster_vectors(self, vectors, layer, affinity_matrix, n_clusters):

        # clustering
        clusterer = SpectralClustering(
            n_clusters=n_clusters, affinity="precomputed_nearest_neighbors",
        )
        cluster_labels = clusterer.fit_predict(affinity_matrix)

        # stats
        silhouette_avg = silhouette_score(vectors, cluster_labels)

        print(
            "Number of Clusters:",
            n_clusters,
            " - The average silhouette_score is :",
            silhouette_avg,
        )

        return cluster_labels

    def find_number_of_clusters(
        self,
        vectors,
        layer,
        max_number_of_clusters=200,
        size_of_candidate_clusters=2,
        plot=False,
    ):

        # clustering
        connectivity = kneighbors_graph(
            vectors, n_neighbors=50, include_self=True, n_jobs=2
        )
        A = 0.5 * (connectivity + connectivity.T)

        # eigengap heursitic

        L = scipy.sparse.csgraph.laplacian(A, normed=True).todense()
        eigenvalues, _ = np.linalg.eig(L)
        eigenvalues = eigenvalues[0:max_number_of_clusters]

        # compute gaps without considering only one cluster
        gaps = np.diff(eigenvalues[1:])

        # order gaps and correct indices
        gaps_indices = np.argsort(gaps)[::-1] + 2

        # select top x candidates and order from small to large
        gaps_indices = np.sort(gaps_indices[:size_of_candidate_clusters])
        optimal_gap = gaps_indices[0]

        # data for plotting the first n
        if plot:
            data = pd.DataFrame(
                {
                    "x": np.arange(len(eigenvalues)) + 1,
                    "y": eigenvalues,
                    "label": np.ones(len(eigenvalues)),
                    "style": "$f$",
                }
            )

            self.plotter.set_layer_and_vector(layer)
            self.plotter.plot_scatter(
                data, title="eigengap plot: " + str(gaps_indices), file_name="eigengap_"
            )

        return optimal_gap, A
