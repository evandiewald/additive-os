// AMProject.cdc
// contract to manage additive manufacturing project data (based on Flow Project standard)
// see: https://docs.onflow.org/cadence/tutorial/04-non-fungible-tokens/

pub contract AMProject {


    // our Project (Non-Fungible-Ticket) is simply defined by an id. metadata coming later
    pub resource Project {
        pub let id: UInt64

        init(initID: UInt64) {
            self.id = initID
        }
    }

    // receiver interface allows others to interact w certain functions via public access
    pub resource interface ProjectOwner {
        pub fun deposit(project: @Project, metadata: String)
        pub fun getIDs(): [UInt64]
        pub fun idExists(id: UInt64): Bool
        pub fun getMetadata(id: UInt64) : String
    }

    // defining a Collection resource for all our tickets
    pub resource Collection: ProjectOwner {
        pub var myProjects: @{UInt64: Project}
        pub var metadataObjs: {UInt64: String}

        init () {
            self.myProjects <- {}
            self.metadataObjs = {}
        }

        pub fun withdraw(withdrawID: UInt64): @Project {
            let project <- self.myProjects.remove(key: withdrawID)!

            return <- project
        }

        pub fun deposit(project: @Project, metadata: String) {
  
            self.metadataObjs[project.id] = metadata

            self.myProjects[project.id] <-! project
        }

        // rest of these are pretty straightforward
        pub fun idExists(id: UInt64): Bool {
            return self.myProjects[id] != nil
        }


        pub fun getIDs(): [UInt64] {
            return self.myProjects.keys
        }

        pub fun updateMetadata(id: UInt64, metadata: String) {
            self.metadataObjs[id] = metadata
        }

        pub fun getMetadata(id: UInt64): String {
            return self.metadataObjs[id]!
        }

        destroy() {
            destroy self.myProjects
        }
    }

    // will need to create an empty collection for any account that wants our Project
    pub fun createEmptyCollection(): @Collection {
        return <- create Collection()
    }

    pub resource interface ProjectInitializer {
        pub fun newProject(): @Project
    }

    // can explicitly share NFTMinter resource with another admin so that they can mint tickets
    pub resource Initializer: ProjectInitializer {
        pub var idCount: UInt64

        init() {
            self.idCount = 1
        }

        pub fun newProject(): @Project {
            var myProject <- create Project(initID: self.idCount)
            self.idCount = self.idCount + 1 as UInt64
            return <- myProject
        }

    }

    pub fun createInitializer(): @Initializer {
        return <- create Initializer()
    }

    // launching the contract does 3 things: 
    init() {
        // 1) save a fresh collection to the admin's storage
        self.account.save(<-self.createEmptyCollection(), to: /storage/ProjectCollection)

        // 2) allow public access to NFTReceiver functions through this reference
        self.account.link<&{ProjectOwner}>(/public/ProjectOwner, target: /storage/ProjectCollection)

        // 3) save NFTMinter resource to private storage
        self.account.save(<-self.createInitializer(), to: /storage/Initializer)

        self.account.link<&{ProjectInitializer}>(/public/ProjectInitializer, target: /storage/Initializer)
    }


}
 