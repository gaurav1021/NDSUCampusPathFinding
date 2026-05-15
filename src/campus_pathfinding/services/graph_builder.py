from __future__ import annotations

from dataclasses import dataclass

import networkx as nx
import pandas as pd


@dataclass(slots=True)
class CampusGraphBundle:
    graph: nx.Graph
    nodes_frame: pd.DataFrame
    edges_frame: pd.DataFrame


class CampusGraphBuilder:
    def build(self, nodes_frame: pd.DataFrame, edges_frame: pd.DataFrame) -> CampusGraphBundle:
        graph = nx.Graph()

        for record in nodes_frame.to_dict(orient="records"):
            graph.add_node(record["node_id"], **record)

        for record in edges_frame.to_dict(orient="records"):
            source = record["source"]
            target = record["target"]
            graph.add_edge(source, target, **record)

        return CampusGraphBundle(graph=graph, nodes_frame=nodes_frame.copy(), edges_frame=edges_frame.copy())
