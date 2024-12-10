WITH first_night_deaths AS (
    SELECT
        m.user_id,
        u.official_nickname,
        a.lobby_id,
        a.passive_user_place AS killed_place
    FROM
        actions a
    JOIN
        members m ON a.lobby_id = m.lobby_id AND a.passive_user_place = m.place
    JOIN
        users u ON m.user_id = u.id
    WHERE
        a.action = 4  -- Shot action
        AND m.game_role = 1  -- Citizen role
        AND a.round = 0  -- First night
    GROUP BY user_id, official_nickname, a.lobby_id, killed_place
),
best_moves AS (
    SELECT
        a.lobby_id,
        a.active_user_place AS recorder_place,
        a.passive_user_place AS recorded_place,
        m_recorder.user_id AS recorder_user_id,
        m_recorded.game_role AS recorded_role
    FROM
        actions a
    JOIN
        members m_recorder ON a.lobby_id = m_recorder.lobby_id AND a.active_user_place = m_recorder.place
    JOIN
        members m_recorded ON a.lobby_id = m_recorded.lobby_id AND a.passive_user_place = m_recorded.place
    WHERE
        a.action = 0  -- Best move action
),
total_black_players AS (
    SELECT
        lobby_id,
        COUNT(*) AS total_black
    FROM
        members
    WHERE
        game_role IN (3, 4)  -- Mafia or Don
    GROUP BY
        lobby_id

),
citizen_best_moves AS (
    SELECT
        fnd.user_id,
        fnd.official_nickname,
--         bm.lobby_id,
--         CASE WHEN bm.recorded_role IN (3, 4) THEN 1 ELSE 0 END,
        COUNT(DISTINCT bm.lobby_id) AS total_best_moves,
        SUM(CASE WHEN bm.recorded_role IN (3, 4) THEN 1 ELSE 0 END) AS black_best_moves,
        tbp.total_black
    FROM
        first_night_deaths fnd
    JOIN
        best_moves bm ON fnd.lobby_id = bm.lobby_id AND fnd.killed_place = bm.recorder_place
    JOIN
        total_black_players tbp ON fnd.lobby_id = tbp.lobby_id
    GROUP BY
        fnd.user_id, fnd.official_nickname, tbp.total_black
)
SELECT
    official_nickname,
    total_best_moves,
    black_best_moves,
    total_black,
    CASE
        WHEN total_black > 0 THEN
            CAST(CAST(black_best_moves AS FLOAT) / (total_black * total_best_moves) * 100 AS NUMERIC(5,2))
        ELSE NULL
    END AS black_best_move_percentage
FROM
    citizen_best_moves
ORDER BY
    black_best_move_percentage DESC, total_best_moves DESC;