CREATE TABLE todos (
    id          SERIAL      PRIMARY KEY,
    title       TEXT        NOT NULL CHECK (length(title) > 0),
    done        BOOLEAN     NOT NULL DEFAULT FALSE,
    due_on      DATE,
    priority    SMALLINT    NOT NULL DEFAULT 2 CHECK (priority BETWEEN 1 AND 3),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_todos_done_due ON todos (done, due_on);

CREATE TABLE tags (
    id   SERIAL PRIMARY KEY,
    name TEXT   UNIQUE NOT NULL CHECK (length(name) > 0)
);

CREATE TABLE todo_tags (
    todo_id INTEGER NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
    PRIMARY KEY (todo_id, tag_id)
);
