package com.leavems;

import javax.swing.*;
import javax.swing.border.EmptyBorder;
import javax.swing.table.DefaultTableModel;
import javax.swing.table.DefaultTableCellRenderer;
import java.awt.*;
import java.awt.geom.RoundRectangle2D;
import java.sql.*;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

public final class LeaveManagementApp {
    private static final Color NAVY = new Color(15, 23, 42);
    private static final Color BLUE = new Color(99, 102, 241);
    private static final Color PURPLE = new Color(139, 92, 246);
    private static final Color CYAN = new Color(34, 211, 238);
    private static final Color BG = new Color(241, 245, 249);
    private static final Color TEXT_MUTED = new Color(100, 116, 139);
    private final JFrame frame = new JFrame("Employee Leave Management System");
    private final LeaveRepository repository;

    public static void main(String[] args) {
        SwingUtilities.invokeLater(() -> {
            UIManager.put("Button.font", new Font("Segoe UI", Font.BOLD, 13));
            UIManager.put("Label.font", new Font("SansSerif", Font.PLAIN, 13));
            UIManager.put("TextField.font", new Font("SansSerif", Font.PLAIN, 13));
            UIManager.put("TabbedPane.selected", Color.WHITE);
            UIManager.put("TabbedPane.contentAreaColor", BG);
            UIManager.put("TabbedPane.focus", new Color(0,0,0,0));
            UIManager.put("Table.selectionBackground", new Color(224, 231, 255));
            UIManager.put("Table.selectionForeground", NAVY);
            new LeaveManagementApp().showLogin();
        });
    }

    LeaveManagementApp() {
        repository = RepositoryFactory.create();
        frame.setDefaultCloseOperation(WindowConstants.EXIT_ON_CLOSE);
        frame.setMinimumSize(new Dimension(950, 620));
        frame.setLocationRelativeTo(null);
    }

    private void showLogin() {
        JPanel root = new GradientPanel(new BorderLayout(), NAVY, new Color(49, 46, 129));
        root.setBackground(BG);
        JPanel brand = new JPanel(); brand.setOpaque(false); brand.setLayout(new BoxLayout(brand, BoxLayout.Y_AXIS));
        brand.setBorder(new EmptyBorder(110, 80, 80, 45));
        JLabel mark = new JLabel("◒  DAYORA"); mark.setForeground(CYAN); mark.setFont(new Font("Segoe UI", Font.BOLD, 18)); mark.setAlignmentX(Component.LEFT_ALIGNMENT);
        JLabel hero = new JLabel("<html>Leave, made<br>beautifully simple.</html>"); hero.setForeground(Color.WHITE); hero.setFont(new Font("Segoe UI", Font.BOLD, 40)); hero.setAlignmentX(Component.LEFT_ALIGNMENT);
        JLabel copy = new JLabel("<html>A calm workspace for your team to plan time away,<br>stay aligned, and return refreshed.</html>"); copy.setForeground(new Color(203,213,225)); copy.setFont(new Font("Segoe UI", Font.PLAIN, 15)); copy.setAlignmentX(Component.LEFT_ALIGNMENT);
        brand.add(mark); brand.add(Box.createVerticalStrut(35)); brand.add(hero); brand.add(Box.createVerticalStrut(22)); brand.add(copy);
        root.add(brand, BorderLayout.CENTER);
        JPanel loginWrap = new JPanel(new GridBagLayout()); loginWrap.setOpaque(false); loginWrap.setBorder(new EmptyBorder(55,35,55,70));
        JPanel card = new RoundPanel(28, Color.WHITE); card.setLayout(new GridBagLayout()); card.setBorder(new EmptyBorder(42, 44, 42, 44));
        GridBagConstraints c = constraints();
        JLabel eyebrow = new JLabel("WELCOME BACK"); eyebrow.setForeground(BLUE); eyebrow.setFont(new Font("Segoe UI",Font.BOLD,11));
        add(card, eyebrow, c, 0, 0, 2);
        JLabel title = new JLabel("Sign in to Dayora"); title.setFont(new Font("Segoe UI", Font.BOLD, 27)); title.setForeground(NAVY);
        add(card, title, c, 0, 1, 2); c.insets = new Insets(15, 5, 5, 5);
        add(card, new JLabel("Username"), c, 0, 2, 2);
        JTextField username = new JTextField(22); styleInput(username); add(card, username, c, 0, 3, 2);
        add(card, new JLabel("Password"), c, 0, 4, 2);
        JPasswordField password = new JPasswordField(22); styleInput(password); add(card, password, c, 0, 5, 2);
        JButton login = primaryButton("Continue  →"); add(card, login, c, 0, 6, 2);
        JLabel mode = new JLabel(repository.description()); mode.setForeground(Color.GRAY);
        add(card, mode, c, 0, 7, 2);
        login.addActionListener(e -> {
            User user = repository.authenticate(username.getText().trim(), new String(password.getPassword()));
            if (user == null) message("Invalid username or password.", JOptionPane.ERROR_MESSAGE);
            else if (user.role().equals("ADMIN")) showAdmin(user); else showEmployee(user);
        });
        password.addActionListener(e -> login.doClick());
        loginWrap.add(card); root.add(loginWrap, BorderLayout.EAST); setContent(root, new Dimension(1080, 680));
    }

    private void showEmployee(User user) {
        JPanel root = shell("Employee Dashboard", user);
        JTabbedPane tabs = styledTabs();
        JPanel requests = new JPanel(new BorderLayout(14, 14)); requests.setBackground(BG); requests.setBorder(new EmptyBorder(24,28,28,28));
        DefaultTableModel model = tableModel("ID", "Type", "From", "To", "Days", "Status", "Admin comment");
        JTable table = table(model); requests.add(new JScrollPane(table), BorderLayout.CENTER);
        JPanel stats = new JPanel(new FlowLayout(FlowLayout.LEFT, 14, 4)); stats.setOpaque(false); requests.add(stats, BorderLayout.NORTH);
        Runnable refresh = () -> {
            model.setRowCount(0); List<LeaveRequest> list = repository.findForEmployee(user.id());
            long pending = 0, approved = 0, rejected = 0;
            for (LeaveRequest r : list) {
                model.addRow(new Object[]{r.id(), r.type(), r.start(), r.end(), r.days(), r.status(), r.comment()});
                if (r.status().equals("PENDING")) pending++; else if (r.status().equals("APPROVED")) approved++; else rejected++;
            }
            stats.removeAll(); stats.add(stat("AWAITING REVIEW", pending, new Color(245,158,11))); stats.add(stat("APPROVED", approved, new Color(16,185,129))); stats.add(stat("DECLINED", rejected, new Color(244,63,94))); stats.revalidate();
        };
        JButton refreshButton = new JButton("Refresh"); refreshButton.addActionListener(e -> refresh.run());
        requests.add(refreshButton, BorderLayout.SOUTH);
        tabs.addTab("My requests", requests);
        tabs.addTab("Apply for leave", applicationForm(user, () -> { refresh.run(); tabs.setSelectedIndex(0); }));
        root.add(tabs, BorderLayout.CENTER); refresh.run(); setContent(root, new Dimension(1050, 680));
    }

    private JPanel applicationForm(User user, Runnable afterSave) {
        JPanel outer = new JPanel(new GridBagLayout()); outer.setBackground(BG);
        JPanel form = new RoundPanel(24, Color.WHITE); form.setLayout(new GridBagLayout()); form.setBorder(new EmptyBorder(32,42,32,42));
        GridBagConstraints c = constraints();
        JComboBox<String> type = new JComboBox<>(new String[]{"Annual", "Sick", "Casual", "Unpaid"});
        JTextField start = new JTextField(LocalDate.now().toString(), 18), end = new JTextField(LocalDate.now().toString(), 18);
        JTextArea reason = new JTextArea(5, 24); reason.setLineWrap(true); reason.setWrapStyleWord(true);
        styleInput(start); styleInput(end); reason.setFont(new Font("Segoe UI",Font.PLAIN,14)); reason.setBorder(new EmptyBorder(10,12,10,12));
        add(form, new JLabel("Leave type"), c, 0, 0, 1); add(form, type, c, 1, 0, 1);
        add(form, new JLabel("Start date (YYYY-MM-DD)"), c, 0, 1, 1); add(form, start, c, 1, 1, 1);
        add(form, new JLabel("End date (YYYY-MM-DD)"), c, 0, 2, 1); add(form, end, c, 1, 2, 1);
        add(form, new JLabel("Reason"), c, 0, 3, 1); add(form, new JScrollPane(reason), c, 1, 3, 1);
        JButton submit = primaryButton("Submit request"); add(form, submit, c, 1, 4, 1);
        submit.addActionListener(e -> {
            try {
                LocalDate from = LocalDate.parse(start.getText().trim()), to = LocalDate.parse(end.getText().trim());
                if (to.isBefore(from)) throw new IllegalArgumentException("End date cannot be before start date.");
                if (reason.getText().isBlank()) throw new IllegalArgumentException("Please enter a reason.");
                repository.create(user.id(), Objects.toString(type.getSelectedItem()), from, to, reason.getText().trim());
                message("Leave request submitted.", JOptionPane.INFORMATION_MESSAGE); reason.setText(""); afterSave.run();
            } catch (Exception ex) { message(ex.getMessage() == null ? "Use valid dates in YYYY-MM-DD format." : ex.getMessage(), JOptionPane.ERROR_MESSAGE); }
        });
        outer.add(form); return outer;
    }

    private void showAdmin(User user) {
        JPanel root = shell("Administrator Dashboard", user);
        JPanel body = new JPanel(new BorderLayout(14,14)); body.setBackground(BG); body.setBorder(new EmptyBorder(24,28,28,28));
        DefaultTableModel model = tableModel("ID", "Employee", "Type", "From", "To", "Days", "Reason", "Status", "Comment");
        JTable table = table(model); body.add(new JScrollPane(table), BorderLayout.CENTER);
        JCheckBox pendingOnly = new JCheckBox("Show pending only", true);
        Runnable refresh = () -> {
            model.setRowCount(0);
            for (LeaveRequest r : repository.findAll(pendingOnly.isSelected()))
                model.addRow(new Object[]{r.id(), r.employee(), r.type(), r.start(), r.end(), r.days(), r.reason(), r.status(), r.comment()});
        };
        pendingOnly.addActionListener(e -> refresh.run()); body.add(pendingOnly, BorderLayout.NORTH);
        JPanel actions = new JPanel(new FlowLayout(FlowLayout.RIGHT)); actions.setOpaque(false);
        JButton refreshBtn = new JButton("Refresh"), reject = new JButton("Reject"), approve = primaryButton("Approve");
        actions.add(refreshBtn); actions.add(reject); actions.add(approve); body.add(actions, BorderLayout.SOUTH);
        refreshBtn.addActionListener(e -> refresh.run());
        approve.addActionListener(e -> decide(table, model, "APPROVED", refresh));
        reject.addActionListener(e -> decide(table, model, "REJECTED", refresh));
        root.add(body, BorderLayout.CENTER); refresh.run(); setContent(root, new Dimension(1150, 700));
    }

    private void decide(JTable table, DefaultTableModel model, String status, Runnable refresh) {
        int row = table.getSelectedRow();
        if (row < 0) { message("Select a request first.", JOptionPane.WARNING_MESSAGE); return; }
        long id = ((Number) model.getValueAt(table.convertRowIndexToModel(row), 0)).longValue();
        String comment = JOptionPane.showInputDialog(frame, "Administrator comment (optional):", status.substring(0,1) + status.substring(1).toLowerCase());
        if (comment == null) return;
        try { repository.decide(id, status, comment.trim()); refresh.run(); message("Request " + status.toLowerCase() + ".", JOptionPane.INFORMATION_MESSAGE); }
        catch (Exception ex) { message(ex.getMessage(), JOptionPane.ERROR_MESSAGE); }
    }

    private JPanel shell(String title, User user) {
        JPanel root = new JPanel(new BorderLayout()); root.setBackground(BG);
        JPanel header = new GradientPanel(new BorderLayout(), NAVY, new Color(49,46,129)); header.setBorder(new EmptyBorder(18,28,18,28));
        JPanel identity = new JPanel(); identity.setOpaque(false); identity.setLayout(new BoxLayout(identity,BoxLayout.Y_AXIS));
        JLabel logo = new JLabel("◒  DAYORA  /  PEOPLE"); logo.setForeground(CYAN); logo.setFont(new Font("Segoe UI",Font.BOLD,11));
        JLabel heading = new JLabel(title); heading.setForeground(Color.WHITE); heading.setFont(new Font("Segoe UI", Font.BOLD, 23));
        identity.add(logo); identity.add(Box.createVerticalStrut(4)); identity.add(heading);
        JPanel right = new JPanel(new FlowLayout()); right.setOpaque(false); JLabel who = new JLabel(user.name()); who.setForeground(Color.WHITE);
        JButton logout = new JButton("Logout"); logout.addActionListener(e -> showLogin()); right.add(who); right.add(logout);
        header.add(identity, BorderLayout.WEST); header.add(right, BorderLayout.EAST); root.add(header, BorderLayout.NORTH); return root;
    }

    private static JPanel stat(String label, long value, Color accent) { JPanel p=new RoundPanel(18,Color.WHITE);p.setLayout(new BorderLayout());p.setBorder(new EmptyBorder(14,18,14,22));JLabel n=new JLabel(String.valueOf(value));n.setFont(new Font("Segoe UI",Font.BOLD,25));n.setForeground(accent);JLabel l=new JLabel(label);l.setFont(new Font("Segoe UI",Font.BOLD,10));l.setForeground(TEXT_MUTED);p.add(n,BorderLayout.CENTER);p.add(l,BorderLayout.SOUTH);return p; }
    private static JTable table(DefaultTableModel m) { JTable t = new JTable(m); t.setRowHeight(38); t.setAutoCreateRowSorter(true); t.setSelectionMode(ListSelectionModel.SINGLE_SELECTION); t.setShowVerticalLines(false);t.setGridColor(new Color(226,232,240));t.setFont(new Font("Segoe UI",Font.PLAIN,13));t.getTableHeader().setFont(new Font("Segoe UI",Font.BOLD,11));t.getTableHeader().setBackground(new Color(248,250,252));t.getTableHeader().setForeground(TEXT_MUTED);t.getTableHeader().setPreferredSize(new Dimension(10,38));t.setDefaultRenderer(Object.class,new StatusRenderer()); return t; }
    private static DefaultTableModel tableModel(String... names) { return new DefaultTableModel(names, 0) { public boolean isCellEditable(int r, int c) { return false; } }; }
    private static JButton primaryButton(String text) { JButton b = new RoundButton(text, BLUE); b.setForeground(Color.WHITE); b.setFocusPainted(false); b.setBorder(new EmptyBorder(11,20,11,20)); return b; }
    private static void styleInput(JTextField field){field.setBorder(BorderFactory.createCompoundBorder(BorderFactory.createLineBorder(new Color(203,213,225)),new EmptyBorder(10,12,10,12)));field.setBackground(new Color(248,250,252));}
    private static JTabbedPane styledTabs(){JTabbedPane t=new JTabbedPane();t.setFont(new Font("Segoe UI",Font.BOLD,13));t.setBackground(BG);t.setBorder(new EmptyBorder(8,18,0,18));return t;}
    private static GridBagConstraints constraints() { GridBagConstraints c = new GridBagConstraints(); c.insets = new Insets(7,5,7,5); c.fill = GridBagConstraints.HORIZONTAL; c.anchor = GridBagConstraints.WEST; return c; }
    private static void add(JPanel p, Component x, GridBagConstraints c, int gx, int gy, int width) { c.gridx=gx; c.gridy=gy; c.gridwidth=width; p.add(x,c); }
    private void setContent(JPanel panel, Dimension size) { frame.setContentPane(panel); frame.setSize(size); frame.setLocationRelativeTo(null); frame.setVisible(true); frame.revalidate(); }
    private void message(String text, int type) { JOptionPane.showMessageDialog(frame, text, "Leave Management", type); }

    static final class GradientPanel extends JPanel {
        private final Color from, to;
        GradientPanel(LayoutManager layout, Color from, Color to){super(layout);this.from=from;this.to=to;setOpaque(false);}
        protected void paintComponent(Graphics g){Graphics2D g2=(Graphics2D)g.create();g2.setRenderingHint(RenderingHints.KEY_RENDERING,RenderingHints.VALUE_RENDER_QUALITY);g2.setPaint(new GradientPaint(0,0,from,getWidth(),getHeight(),to));g2.fillRect(0,0,getWidth(),getHeight());g2.dispose();super.paintComponent(g);}
    }

    static class RoundPanel extends JPanel {
        private final int radius; private final Color fill;
        RoundPanel(int radius,Color fill){this.radius=radius;this.fill=fill;setOpaque(false);}
        protected void paintComponent(Graphics g){Graphics2D g2=(Graphics2D)g.create();g2.setRenderingHint(RenderingHints.KEY_ANTIALIASING,RenderingHints.VALUE_ANTIALIAS_ON);g2.setColor(new Color(15,23,42,18));g2.fillRoundRect(2,4,getWidth()-4,getHeight()-5,radius,radius);g2.setColor(fill);g2.fillRoundRect(0,0,getWidth()-3,getHeight()-4,radius,radius);g2.dispose();super.paintComponent(g);}
    }

    static final class RoundButton extends JButton {
        private final Color fill;
        RoundButton(String text,Color fill){super(text);this.fill=fill;setContentAreaFilled(false);setOpaque(false);setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));}
        protected void paintComponent(Graphics g){Graphics2D g2=(Graphics2D)g.create();g2.setRenderingHint(RenderingHints.KEY_ANTIALIASING,RenderingHints.VALUE_ANTIALIAS_ON);g2.setColor(getModel().isPressed()?fill.darker():getModel().isRollover()?fill.brighter():fill);g2.fill(new RoundRectangle2D.Float(0,0,getWidth(),getHeight(),14,14));g2.dispose();super.paintComponent(g);}
    }

    static final class StatusRenderer extends DefaultTableCellRenderer {
        public Component getTableCellRendererComponent(JTable table,Object value,boolean selected,boolean focus,int row,int col){
            JLabel label=(JLabel)super.getTableCellRendererComponent(table,value,selected,focus,row,col);label.setBorder(new EmptyBorder(0,10,0,10));
            if(!selected){label.setBackground(row%2==0?Color.WHITE:new Color(248,250,252));label.setForeground(NAVY);}
            String text=Objects.toString(value,"");
            if(!selected&&text.equals("APPROVED"))label.setForeground(new Color(5,150,105));
            else if(!selected&&text.equals("REJECTED"))label.setForeground(new Color(225,29,72));
            else if(!selected&&text.equals("PENDING"))label.setForeground(new Color(217,119,6));
            return label;
        }
    }

    record User(long id, String username, String name, String role) {}
    record LeaveRequest(long id, long employeeId, String employee, String type, LocalDate start, LocalDate end, String reason, String status, String comment) {
        long days() { return ChronoUnit.DAYS.between(start, end) + 1; }
    }

    interface LeaveRepository {
        User authenticate(String username, String password);
        void create(long employeeId, String type, LocalDate start, LocalDate end, String reason);
        List<LeaveRequest> findForEmployee(long employeeId);
        List<LeaveRequest> findAll(boolean pendingOnly);
        void decide(long id, String status, String comment);
        String description();
    }

    static final class RepositoryFactory {
        static LeaveRepository create() {
            String url = System.getenv().getOrDefault("LEAVE_DB_URL", "jdbc:mysql://localhost:3306/leave_management");
            try { JdbcRepository repo = new JdbcRepository(url, System.getenv().getOrDefault("LEAVE_DB_USER", "root"), System.getenv().getOrDefault("LEAVE_DB_PASSWORD", "")); repo.test(); return repo; }
            catch (Exception ignored) { return new MemoryRepository(); }
        }
    }

    static final class JdbcRepository implements LeaveRepository {
        private final String url, user, password;
        JdbcRepository(String url, String user, String password) { this.url=url; this.user=user; this.password=password; }
        Connection connection() throws SQLException { return DriverManager.getConnection(url, user, password); }
        void test() throws SQLException { try (Connection ignored = connection()) {} }
        public User authenticate(String username, String password) {
            String sql="SELECT id,username,full_name,role FROM users WHERE username=? AND password=?";
            try(Connection c=connection(); PreparedStatement p=c.prepareStatement(sql)){ p.setString(1,username);p.setString(2,password);try(ResultSet r=p.executeQuery()){return r.next()?new User(r.getLong(1),r.getString(2),r.getString(3),r.getString(4)):null;}} catch(SQLException e){throw db(e);}
        }
        public void create(long eid,String type,LocalDate start,LocalDate end,String reason){String sql="INSERT INTO leave_requests(employee_id,leave_type,start_date,end_date,reason) VALUES(?,?,?,?,?)";try(Connection c=connection();PreparedStatement p=c.prepareStatement(sql)){p.setLong(1,eid);p.setString(2,type);p.setDate(3,Date.valueOf(start));p.setDate(4,Date.valueOf(end));p.setString(5,reason);p.executeUpdate();}catch(SQLException e){throw db(e);}}
        public List<LeaveRequest> findForEmployee(long id){return query("WHERE l.employee_id=? ORDER BY l.created_at DESC",p->p.setLong(1,id));}
        public List<LeaveRequest> findAll(boolean pending){return query((pending?"WHERE l.status='PENDING' ":"")+"ORDER BY l.created_at DESC",p->{});}
        private List<LeaveRequest> query(String suffix, SqlSetter setter){String sql="SELECT l.id,l.employee_id,u.full_name,l.leave_type,l.start_date,l.end_date,l.reason,l.status,COALESCE(l.admin_comment,'') FROM leave_requests l JOIN users u ON u.id=l.employee_id "+suffix;List<LeaveRequest>x=new ArrayList<>();try(Connection c=connection();PreparedStatement p=c.prepareStatement(sql)){setter.set(p);try(ResultSet r=p.executeQuery()){while(r.next())x.add(new LeaveRequest(r.getLong(1),r.getLong(2),r.getString(3),r.getString(4),r.getDate(5).toLocalDate(),r.getDate(6).toLocalDate(),r.getString(7),r.getString(8),r.getString(9)));}return x;}catch(SQLException e){throw db(e);}}
        public void decide(long id,String status,String comment){String sql="UPDATE leave_requests SET status=?,admin_comment=?,decided_at=CURRENT_TIMESTAMP WHERE id=? AND status='PENDING'";try(Connection c=connection();PreparedStatement p=c.prepareStatement(sql)){p.setString(1,status);p.setString(2,comment);p.setLong(3,id);if(p.executeUpdate()==0)throw new IllegalStateException("Request was already processed.");}catch(SQLException e){throw db(e);}}
        public String description(){return "Connected to MySQL";}
        private static RuntimeException db(SQLException e){return new IllegalStateException("Database error: "+e.getMessage(),e);}
        interface SqlSetter{void set(PreparedStatement p)throws SQLException;}
    }

    static final class MemoryRepository implements LeaveRepository {
        private final List<User> users=List.of(new User(1,"admin","System Administrator","ADMIN"),new User(2,"employee","Demo Employee","EMPLOYEE"));
        private final List<LeaveRequest> leaves=new ArrayList<>(); private long next=1;
        public User authenticate(String u,String p){return users.stream().filter(x->x.username().equals(u)&&p.equals(x.role().equals("ADMIN")?"admin123":"employee123")).findFirst().orElse(null);}
        public synchronized void create(long eid,String type,LocalDate start,LocalDate end,String reason){String name=users.stream().filter(u->u.id()==eid).findFirst().orElseThrow().name();leaves.add(new LeaveRequest(next++,eid,name,type,start,end,reason,"PENDING",""));}
        public synchronized List<LeaveRequest> findForEmployee(long eid){return leaves.stream().filter(x->x.employeeId()==eid).toList();}
        public synchronized List<LeaveRequest> findAll(boolean pending){return leaves.stream().filter(x->!pending||x.status().equals("PENDING")).toList();}
        public synchronized void decide(long id,String status,String comment){for(int i=0;i<leaves.size();i++){LeaveRequest x=leaves.get(i);if(x.id()==id){if(!x.status().equals("PENDING"))throw new IllegalStateException("Request was already processed.");leaves.set(i,new LeaveRequest(x.id(),x.employeeId(),x.employee(),x.type(),x.start(),x.end(),x.reason(),status,comment));return;}}throw new IllegalArgumentException("Request not found.");}
        public String description(){return "Demo mode (MySQL not connected)";}
    }
}
