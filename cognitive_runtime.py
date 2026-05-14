

from pydantic import (
    BaseModel,
    Field,
)
from collections import deque

class NodeResult(BaseModel):

    updated_state: dict = Field(
        default_factory=dict
    )

    suggested_next_nodes: list[str] = Field(
        default_factory=list
    )

    revisit_nodes: list[str] = Field(
        default_factory=list
    )

    uncertainty_delta: float = 0.0

    confidence: float = 0.5

    terminate: bool = False

    reasoning: list[str] = Field(
        default_factory=list
    )


NODE_REGISTRY = {}


def register_node(
    name: str,
):
    def decorator(func):

        NODE_REGISTRY[name] = func

        return func

    return decorator




class NodeResult(BaseModel):

    updated_state: dict = Field(
        default_factory=dict
    )

    suggested_next_nodes: list[str] = Field(
        default_factory=list
    )

    revisit_nodes: list[str] = Field(
        default_factory=list
    )

    uncertainty_delta: float = 0.0

    confidence: float = 0.5

    terminate: bool = False

    reasoning: list[str] = Field(
        default_factory=list
    )


def execute_graph_runtime(
    initial_state,
):

    execution_queue = deque(
        ["business_profile"]
    )

    visited = []

    state = initial_state

    while execution_queue:

        node_name = (
            execution_queue.popleft()
        )

        if node_name not in NODE_REGISTRY:
            continue

        node_fn = NODE_REGISTRY[
            node_name
        ]

        result = node_fn(state)

        visited.append(node_name)

        if isinstance(
            result,
            NodeResult,
        ):

            for key, value in (
                result.updated_state.items()
            ):

                setattr(
                    state,
                    key,
                    value,
                )

            state.uncertainty_score += (
                result.uncertainty_delta
            )

            state.reasoning_notes.extend(
                result.reasoning
            )

            if result.terminate:
                break

            for revisit in (
                result.revisit_nodes
            ):
                execution_queue.appendleft(
                    revisit
                )

            for next_node in (
                result.suggested_next_nodes
            ):
                execution_queue.append(
                    next_node
                )

        else:
            state = result

    state.execution_trace = visited

    return state