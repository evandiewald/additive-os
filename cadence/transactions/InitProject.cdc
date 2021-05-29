import AMProject from 0x5cc83cb6d766bf4a

// This transaction allows the Minter account to mint an NFT
// and deposit it into its collection.

transaction {

    // The reference to the collection that will be receiving the NFT
    let receiverRef: &{AMProject.ProjectOwner}

    // The reference to the Minter resource stored in account storage
    // let initializerRef: &{AMProject.ProjectInitializer}
    let initializerRef: &{AMProject.ProjectInitializer}

    prepare(acct: AuthAccount) {
        // Get the owner's collection capability and borrow a reference
        self.receiverRef = acct.getCapability<&{AMProject.ProjectOwner}>(/public/ProjectOwner)
            .borrow()
            ?? panic("Could not borrow receiver reference")
        // self.initializerRef = acct.borrow<&AMProject.Initializer>(from: /storage/Initializer)
        // Borrow a capability for the NFTMinter in storage
        self.initializerRef = acct.getCapability<&{AMProject.ProjectInitializer}>(/public/ProjectInitializer).borrow()
            ?? panic("Could not borrow initializer reference")
        // self.initializerRef = acct.borrow<&AMProject.Initializer>(from: /storage/ProjectInitializer)
        //     ?? panic("Could not borrow initializer reference")
    }

    execute {
        // Use the minter reference to mint an NFT, which deposits
        // the NFT into the collection that is sent as a parameter.
        let myProject <- self.initializerRef.newProject()

        let metadata : String = ""
        
        self.receiverRef.deposit(project: <-myProject, metadata: metadata)

        log("Ticket minted and deposited into admin account")
    }
}