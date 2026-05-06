INSERT INTO todos (title, due_on, priority) VALUES
    ('牛乳を買う',          CURRENT_DATE + 1, 2),
    ('健康診断の予約',      CURRENT_DATE + 2, 1),
    ('過去の領収書を整理',  NULL,             3),
    ('家賃を振り込む',      CURRENT_DATE + 18, 1);

INSERT INTO tags (name) VALUES ('家事'), ('仕事'), ('健康')
ON CONFLICT DO NOTHING;

INSERT INTO todo_tags (todo_id, tag_id)
SELECT t.id, g.id
  FROM todos t
  JOIN tags  g ON g.name = '家事'
 WHERE t.title = '牛乳を買う'
ON CONFLICT DO NOTHING;

INSERT INTO todo_tags (todo_id, tag_id)
SELECT t.id, g.id
  FROM todos t
  JOIN tags  g ON g.name = '健康'
 WHERE t.title = '健康診断の予約'
ON CONFLICT DO NOTHING;
